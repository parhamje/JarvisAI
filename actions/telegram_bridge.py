"""
telegram_bridge.py — Jarvis Inbound Telegram Bridge

Lets you control Jarvis remotely from Telegram: send a message that starts with
the trigger word "jarvis" (or Persian "جارویس") from ANY of your chats, and the
command is injected into the live Gemini session. The turn's reply is sent back
to the SAME chat as a text message plus a voice note.

Only YOUR OWN (outgoing) messages can trigger it — incoming messages from other
people are ignored. It reuses the already-authenticated Telethon userbot from
telegram_control.py (shared client + background event loop).

⚠️ Privacy note: triggering "jarvis ..." inside someone else's chat will post the
reply (text + voice note) into THAT chat, visible to them.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Optional, Tuple

# Gemini reply audio format (matches RECEIVE_SAMPLE_RATE / CHANNELS in main.py)
_PCM_RATE     = 24_000
_PCM_CHANNELS = 1
_PCM_WIDTH    = 2          # int16

# Triggers (case-insensitive). English + Persian.
_TRIGGERS = ("jarvis", "جارویس")

# How long to wait for a Gemini turn to complete before giving up.
_TURN_TIMEOUT = 120


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


class TelegramBridge:
    """Listens on the userbot for trigger-word commands and routes Jarvis's
    reply (text + voice note) back to the originating chat."""

    def __init__(self, jarvis):
        self.jarvis      = jarvis          # JarvisLive instance
        self._me_id: Optional[int] = None
        self._turn_lock  = threading.Lock()  # one in-flight remote turn at a time
        self._client     = None
        self._loop       = None            # Telethon background loop

    # ── startup ───────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Register the message handler on the shared Telethon loop.
        Returns True if the bridge is live, False if Telegram isn't ready."""
        try:
            from actions.telegram_control import get_client_and_loop
            from telethon import events
        except Exception as e:
            print(f"[TGBridge] Telethon unavailable — bridge disabled: {e}")
            return False

        client, loop = get_client_and_loop()
        self._client = client
        self._loop   = loop

        async def _register() -> bool:
            await client.connect()
            if not await client.is_user_authorized():
                print("[TGBridge] Telegram not authorized — bridge disabled. "
                      "Log in via the telegram_control tool first.")
                return False
            me = await client.get_me()
            self._me_id = me.id
            client.add_event_handler(
                self._on_new_message,
                events.NewMessage(outgoing=True, incoming=False),
            )
            name = getattr(me, "first_name", "you")
            print(f"[TGBridge] Listening for '{'/'.join(_TRIGGERS)}' commands from {name}.")
            return True

        try:
            return asyncio.run_coroutine_threadsafe(_register(), loop).result(timeout=30)
        except Exception as e:
            print(f"[TGBridge] Registration failed — bridge disabled: {e}")
            return False

    # ── trigger parsing ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_trigger(text: str) -> Optional[str]:
        """If `text` starts with a trigger word, return the command remainder.
        Returns None if there's no trigger or the command is empty."""
        if not text:
            return None
        stripped = text.strip()
        lower    = stripped.lower()
        for trig in _TRIGGERS:
            if lower.startswith(trig):
                rest = stripped[len(trig):]
                # Require the trigger to be its own token (space/punct/end after it),
                # so words like "jarvisson" don't match.
                if rest and not rest[0].isspace() and rest[0] not in ",:،.!?-":
                    continue
                command = rest.lstrip(" \t,:،.!?-")
                return command or None
        return None

    # ── inbound handler (runs on the Telethon loop — must not block) ────────────

    async def _on_new_message(self, event):
        try:
            # Security gate: only the user's own outgoing messages.
            if not event.out:
                return
            command = self._parse_trigger(event.raw_text or "")
            if not command:
                return
            chat_id = event.chat_id
            print(f"[TGBridge] 📥 Command from chat {chat_id}: {command[:80]}")
            threading.Thread(
                target=self._handle_command,
                args=(chat_id, command),
                daemon=True,
            ).start()
        except Exception as e:
            print(f"[TGBridge] handler error: {e}")

    # ── command worker (own thread — safe to block; on neither event loop) ──────

    def _handle_command(self, chat_id, command_text: str):
        if not self._turn_lock.acquire(blocking=False):
            self._send_text(chat_id, "One moment, Sir — still finishing the last request.")
            return
        try:
            done   = threading.Event()
            result: dict = {}

            def on_complete(transcript: str, pcm: bytes):
                result["transcript"] = transcript
                result["pcm"]        = pcm
                done.set()

            if not self.jarvis.begin_telegram_turn(on_complete):
                self._send_text(chat_id, "Busy with another remote turn, Sir.")
                return

            # Inject into the SAME live Gemini session the PC uses.
            self.jarvis._on_text_command(command_text)

            if not done.wait(timeout=_TURN_TIMEOUT):
                # Disarm the stale routing so the next command isn't poisoned.
                with self.jarvis._tg_route_lock:
                    self.jarvis._tg_active      = False
                    self.jarvis._tg_on_complete = None
                    self.jarvis._tg_audio_buf   = []
                self._send_text(chat_id, "That took too long, Sir; the reply was dropped.")
                return

            transcript = (result.get("transcript") or "").strip()
            pcm        = result.get("pcm") or b""

            if transcript:
                self._send_text(chat_id, transcript)

            if pcm:
                path, kind = self._encode_voice_note(pcm)
                if path and kind == "ogg":
                    self._send_voice(chat_id, path)
                elif path and kind == "wav":
                    self._send_file(chat_id, path)
        except Exception as e:
            print(f"[TGBridge] command error: {e}")
            try:
                self._send_text(chat_id, f"Sir, something went wrong: {e}")
            except Exception:
                pass
        finally:
            self._turn_lock.release()

    # ── audio pipeline ──────────────────────────────────────────────────────────

    def _encode_voice_note(self, pcm: bytes) -> Tuple[Optional[Path], str]:
        """Turn raw 24kHz mono int16 PCM into a Telegram-ready file.
        Returns (path, "ogg") for an Opus voice note, (path, "wav") for a
        plain-file fallback, or (None, "") if nothing could be produced."""
        if not pcm:
            return None, ""

        # 1. Write a temp WAV (stdlib — no ffmpeg needed).
        try:
            fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_tg_")
            os.close(fd)
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(_PCM_CHANNELS)
                wf.setsampwidth(_PCM_WIDTH)
                wf.setframerate(_PCM_RATE)
                wf.writeframes(pcm)
        except Exception as e:
            print(f"[TGBridge] WAV write failed: {e}")
            return None, ""

        # 2. Convert to OGG/Opus for a proper round voice note.
        if _ffmpeg_available():
            try:
                from pydub import AudioSegment
                ogg_path = wav_path[:-4] + ".ogg"
                audio = AudioSegment.from_wav(wav_path)
                audio.export(
                    ogg_path, format="ogg", codec="libopus",
                    parameters=["-application", "voip"],
                )
                try:
                    os.remove(wav_path)
                except Exception:
                    pass
                return Path(ogg_path), "ogg"
            except Exception as e:
                print(f"[TGBridge] Opus encode failed, sending WAV instead: {e}")

        # 3. Fallback: send the WAV as a normal file.
        return Path(wav_path), "wav"

    # ── outbound senders (wrap Telethon coroutines onto its loop) ───────────────

    def _send_text(self, chat_id, text: str):
        try:
            asyncio.run_coroutine_threadsafe(
                self._client.send_message(chat_id, text), self._loop
            ).result(timeout=30)
        except Exception as e:
            print(f"[TGBridge] send_text failed: {e}")

    def _send_voice(self, chat_id, path: Path):
        try:
            asyncio.run_coroutine_threadsafe(
                self._client.send_file(chat_id, str(path), voice_note=True), self._loop
            ).result(timeout=60)
        except Exception as e:
            print(f"[TGBridge] send_voice failed: {e}")
        finally:
            self._cleanup(path)

    def _send_file(self, chat_id, path: Path):
        try:
            asyncio.run_coroutine_threadsafe(
                self._client.send_file(chat_id, str(path)), self._loop
            ).result(timeout=60)
        except Exception as e:
            print(f"[TGBridge] send_file failed: {e}")
        finally:
            self._cleanup(path)

    @staticmethod
    def _cleanup(path: Path):
        try:
            os.remove(path)
        except Exception:
            pass
