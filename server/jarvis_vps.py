"""
jarvis_vps.py — Always-on, headless JARVIS brain for a Linux VPS.

This is the "Phase 1" server: it runs the JARVIS personality + Gemini reasoning
+ long-term memory + a set of CLOUD-SAFE tools, and is driven entirely through
Telegram. There is NO GUI, NO microphone, NO speakers, and NO PC-control tools
here — those only exist on the PC client (a later phase), because they
physically require your computer to be awake.

How you talk to it:
    In ANY Telegram chat, send a message that STARTS WITH "jarvis" or "جارویس",
    e.g.  "jarvis what's the weather in Amsterdam"
          "جارویس به علی بگو من دیر میام"
    The userbot (your own account) sees your outgoing message, runs it through
    the brain, and replies in the same chat.

Security: it ONLY reacts to YOUR OWN outgoing messages (events.NewMessage with
outgoing=True). Nobody else can trigger it — they cannot send messages from
your account.

Run it:
    # from the repository root, on the VPS
    python -m server.jarvis_vps            # normal run
    python -m server.jarvis_vps --login    # first-time interactive Telegram login
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz
from telethon.tl.functions.account import UpdateProfileRequest

# ── Make the repository root importable (so `actions`, `memory`, `core` resolve)
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from google import genai  # noqa: E402

from telethon import TelegramClient, events  # noqa: E402

# Reuse the existing, battle-tested helpers from the PC app ─────────────────────
from memory.memory_manager import (  # noqa: E402
    load_memory, format_memory_for_prompt, remember as mem_remember,
    forget as mem_forget,
)
from actions.telegram_control import (  # noqa: E402
    _resolve_entity_async, _fmt_msg,
)


# ── Paths & config ─────────────────────────────────────────────────────────────

CONFIG_PATH  = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH  = BASE_DIR / "core" / "prompt.txt"
SESSION_PATH = str(BASE_DIR / "jarvis.session")   # reuse the same session file

TEXT_MODEL   = "gemini-2.5-flash"                  # light, fast, cheap — good for a 1GB VPS
TRIGGERS     = ("jarvis", "جارویس")                # message must start with one of these
HISTORY_MAX  = 12                                  # messages of context kept per chat
MAX_TOOL_HOPS = 6                                  # safety cap on function-call loops


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[VPS] ⚠️ Could not read config: {e}")
        return {}


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Parham's AI assistant. Be concise, direct, and helpful. "
            "Address the user as 'Sir'. Always use the provided tools to get real data — "
            "never guess or fabricate results."
        )


# ── Cloud-safe tool declarations (what the model is allowed to call) ────────────
# NOTE: deliberately NO open_app / computer_control / screen / games / files here.
# Those need the PC and belong to the PC client, not this always-on server.

TOOL_DECLARATIONS = [
    {
        "name": "web_search",
        "description": "Search the web / internet for any up-to-date information, news, facts, prices, or research.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "A clear, focused search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get the current weather or forecast for a city.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"},
                "when": {"type": "STRING", "description": "today | tomorrow | this week (optional)"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "send_telegram",
        "description": (
            "Send a Telegram message to one of the user's contacts, groups, or channels, "
            "acting as the user themselves."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING", "description": "Contact name, @username, or phone number"},
                "text":     {"type": "STRING", "description": "The message text to send"},
            },
            "required": ["receiver", "text"],
        },
    },
    {
        "name": "read_telegram",
        "description": "Read the last N messages from a specific Telegram chat/contact.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chat":  {"type": "STRING", "description": "Chat or contact name / @username"},
                "limit": {"type": "INTEGER", "description": "How many recent messages (default 10)"},
            },
            "required": ["chat"],
        },
    },
    {
        "name": "get_unread",
        "description": "List Telegram chats that currently have unread messages, with a preview.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "remember",
        "description": (
            "Save an important long-term fact about the user (name, preference, project, "
            "relationship, plan). Call silently when the user reveals something worth keeping."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "identity | preferences | projects | relationships | wishes | notes"},
                "key":      {"type": "STRING", "description": "Short snake_case key, e.g. favorite_food"},
                "value":    {"type": "STRING", "description": "Concise value in English"},
            },
            "required": ["category", "key", "value"],
        },
    },
    {
        "name": "recall",
        "description": "Look up what JARVIS already knows about the user (returns stored long-term memory).",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_time",
        "description": "Get the current date and time.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "open_app",
        "description": "Opens an application or website on the user's local PC. Requires PC to be online.",
        "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING"}}, "required": ["app_name"]},
    },
    {
        "name": "computer_settings",
        "description": "Controls local PC settings (volume, close app, play/pause media, shutdown, restart). Requires PC to be online.",
        "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "e.g. volume_up, pause, close_app, shutdown, restart"}, "value": {"type": "STRING"}}, "required": ["action"]},
    },
]


# ── The brain ──────────────────────────────────────────────────────────────────

class JarvisVPS:
    def __init__(self):
        cfg = _load_config()
        self.api_key  = cfg.get("gemini_api_key", "")
        self.api_id   = int(cfg.get("telegram_api_id", 0) or 0)
        self.api_hash = cfg.get("telegram_api_hash", "")
        self.phone    = cfg.get("telegram_phone", "")

        if not self.api_key:
            raise SystemExit("[VPS] ❌ gemini_api_key missing in config/api_keys.json")
        if not self.api_id or not self.api_hash:
            raise SystemExit(
                "[VPS] ❌ telegram_api_id / telegram_api_hash missing in config/api_keys.json.\n"
                "       Get them from https://my.telegram.org → API development tools."
            )

        self.client = genai.Client(api_key=self.api_key)
        self.tg     = TelegramClient(SESSION_PATH, self.api_id, self.api_hash)

        # Per-chat short conversation history: {chat_id: [genai Content-like dicts]}
        self._history: dict[int, list] = {}

    # ── system prompt assembled fresh each turn (so memory/time stay current) ──
    def _system_instruction(self) -> str:
        sys_prompt = _load_system_prompt()
        mem_str    = format_memory_for_prompt(load_memory())
        now        = datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")

        channel_note = (
            "[CHANNEL] You are running headless on a 24/7 server and replying over "
            "Telegram text. You have NO screen, NO microphone, and CANNOT control the "
            "user's PC (no opening apps, files, mouse, or games) — that hardware is "
            "offline. If asked to do something that needs the PC, say it requires the PC "
            "to be online and offer a cloud alternative. Keep replies short and chat-like."
        )
        time_note = f"[CURRENT DATE & TIME]\nRight now it is: {now}\n"

        parts = [time_note, channel_note]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        return "\n\n".join(parts)

    # ── tool execution (all blocking calls; run off the event loop) ────────────
    def _exec_tool(self, name: str, args: dict) -> str:
        try:
            if name == "web_search":
                from actions.web_search import web_search
                return web_search(parameters={"query": args.get("query", "")}, player=None) or "No results."

            if name == "get_weather":
                # No browser on a VPS, so answer via grounded web search.
                from actions.web_search import web_search
                city = args.get("city", "")
                when = args.get("when", "today")
                return web_search(parameters={"query": f"weather in {city} {when}"}, player=None) or "No weather data."

            if name == "send_telegram":
                receiver = args.get("receiver", "")
                text     = args.get("text", "")
                if not receiver or not text:
                    return "Missing receiver or text."
                entity = self._run_tg(_resolve_entity_async(self.tg, receiver))
                self._run_tg(self.tg.send_message(entity, text))
                return f"Message sent to {receiver}."

            if name == "read_telegram":
                chat  = args.get("chat", "")
                limit = int(args.get("limit", 10) or 10)
                entity   = self._run_tg(_resolve_entity_async(self.tg, chat))
                messages = self._run_tg(self.tg.get_messages(entity, limit=limit))
                if not messages:
                    return f"No messages found in {chat}."
                lines = [_fmt_msg(m) for m in reversed(messages) if (m.text or m.media)]
                return f"Last messages from {chat}:\n" + "\n".join(lines)

            if name == "get_unread":
                dialogs = self._run_tg(self.tg.get_dialogs(limit=50))
                unread  = [d for d in dialogs if d.unread_count > 0]
                if not unread:
                    return "No unread messages."
                lines = []
                for d in unread[:10]:
                    nm = getattr(d.entity, "title", None) or \
                         f"{getattr(d.entity, 'first_name', '')} {getattr(d.entity, 'last_name', '')}".strip()
                    lines.append(f"• {nm} ({d.unread_count} unread)")
                return "Unread chats:\n" + "\n".join(lines)

            if name == "remember":
                return mem_remember(
                    args.get("key", ""), args.get("value", ""), args.get("category", "notes")
                )

            if name == "recall":
                mem = format_memory_for_prompt(load_memory())
                return mem or "I have no stored memories yet, Sir."

            if name == "get_time":
                return datetime.now().strftime("It is %A, %B %d, %Y, %I:%M %p.")

            if name in ["open_app", "computer_settings", "desktop_control", "computer_control"]:
                cmd_json = json.dumps({"tool": name, "args": args})
                # Send command to Saved Messages ('me')
                msg = self._run_tg(self.tg.send_message('me', f"[VPS_CMD] {cmd_json}"))
                
                # Wait up to 15 seconds for a [VPS_RES] reply
                for _ in range(15):
                    time.sleep(1)
                    recent = self._run_tg(self.tg.get_messages('me', limit=5))
                    for m in recent:
                        if m.text and m.text.startswith("[VPS_CMD]") and "[VPS_RES]" in m.text:
                            # Verify it's the response to our specific message
                            if m.id == msg.id:
                                res_str = m.text.split("[VPS_RES]")[1].strip()
                                try:
                                    res_data = json.loads(res_str)
                                    return res_data.get("result", "Done.")
                                except Exception:
                                    pass
                return "The PC Node did not respond in time. It might be offline."

            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Tool '{name}' failed: {e}"

    # ── run a Telethon coroutine from the (sync) tool executor ─────────────────
    def _run_tg(self, coro):
        # We are inside run_in_executor (a worker thread); the Telethon client
        # lives on the main asyncio loop, so hand the coroutine back to it.
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=45)

    # ── one full reasoning turn for a single user command ──────────────────────
    def _think(self, chat_id: int, command: str) -> str:
        from google.genai import types

        history = self._history.setdefault(chat_id, [])
        history.append(types.Content(role="user", parts=[types.Part(text=command)]))

        config = {
            "system_instruction": self._system_instruction(),
            "tools": [{"function_declarations": TOOL_DECLARATIONS}],
            "temperature": 0.7,
        }

        final_text = ""
        for _ in range(MAX_TOOL_HOPS):
            resp = self.client.models.generate_content(
                model=TEXT_MODEL, contents=history, config=config
            )
            cand = resp.candidates[0] if resp.candidates else None
            if not cand or not cand.content:
                break

            history.append(cand.content)

            calls = [p.function_call for p in (cand.content.parts or []) if getattr(p, "function_call", None)]
            if not calls:
                # No tool calls → this is the final answer.
                final_text = (resp.text or "").strip()
                break

            # Execute every requested tool, then feed results back to the model.
            tool_parts = []
            for fc in calls:
                name = fc.name
                args = dict(fc.args or {})
                print(f"[VPS] 🔧 {name} {args}")
                result = self._exec_tool(name, args)
                print(f"[VPS] 📤 {name} → {str(result)[:80]}")
                tool_parts.append(
                    types.Part.from_function_response(name=name, response={"result": result})
                )
            history.append(types.Content(role="user", parts=tool_parts))

        # Trim history so RAM/context stays bounded. Drop from the front, but
        # never start on a dangling tool/model turn — Gemini requires the first
        # turn to be a plain user message, and a function_response must follow
        # its function_call. So advance the cut to the next clean user-text turn.
        if len(history) > HISTORY_MAX:
            cut = len(history) - HISTORY_MAX
            while cut < len(history) and not self._is_user_text(history[cut]):
                cut += 1
            self._history[chat_id] = history[cut:]

        return final_text or "Done, Sir."

    @staticmethod
    def _is_user_text(content) -> bool:
        """True if this turn is a plain user text message (safe history start)."""
        if getattr(content, "role", None) != "user":
            return False
        parts = getattr(content, "parts", None) or []
        return any(getattr(p, "text", None) for p in parts) and \
            not any(getattr(p, "function_response", None) for p in parts)

    async def _clock_loop(self, base_name: str):
        tz = pytz.timezone("Asia/Tehran")
        mapping = {'0': '𝟘', '1': '𝟙', '2': '𝟚', '3': '𝟛', '4': '𝟜', 
                   '5': '𝟝', '6': '𝟞', '7': '𝟟', '8': '𝟠', '9': '𝟡', ':': ':'}
        while True:
            try:
                now = datetime.now(tz)
                time_str = now.strftime("%H:%M")
                styled_time = "".join(mapping.get(c, c) for c in time_str)
                new_name = f"{base_name} {styled_time}".strip()
                
                # Fetch current me to check if we really need to update (saves API calls)
                me = await self.tg.get_me()
                current_name = getattr(me, "first_name", "") or ""
                if current_name != new_name:
                    await self.tg(UpdateProfileRequest(first_name=new_name))
            except Exception as e:
                print(f"[VPS] ❌ Clock update failed: {e}")
            
            # Wait until the start of the next minute
            now = datetime.now()
            sleep_sec = 60 - now.second
            await asyncio.sleep(sleep_sec)

    # ── Telegram wiring ────────────────────────────────────────────────────────
    @staticmethod
    def _strip_trigger(text: str) -> Optional[str]:
        """Return the command after the trigger word, or None if not triggered."""
        stripped = (text or "").strip()
        low = stripped.lower()
        for trig in TRIGGERS:
            if low.startswith(trig.lower()):
                return stripped[len(trig):].lstrip(" ,:.،-—").strip()
        return None

    async def _on_message(self, event):
        if event.raw_text and (event.raw_text.startswith("[VPS_CMD]") or event.raw_text.startswith("[VPS_RES]")):
            return

        command = self._strip_trigger(event.raw_text)
        if command is None:
            return  # not addressed to JARVIS — ignore
        if not command:
            reply_text = "بله قربان؟" if "جارویس" in event.raw_text else "Yes, Sir? Give me a command."
            edited_text = f"{event.raw_text}\n\n🤖: {reply_text}"
            try:
                await event.edit(edited_text)
            except Exception:
                await event.reply(reply_text)
            return

        chat_id = event.chat_id
        print(f"\n[VPS] 💬 ({chat_id}) {command}")
        try:
            # Reasoning is blocking (sync google-genai), so keep the loop responsive.
            answer = await self._loop.run_in_executor(None, self._think, chat_id, command)
        except Exception as e:
            answer = f"I hit an error, Sir: {e}"
            print(f"[VPS] ❌ {e}")

        # Telegram hard-limits messages to 4096 chars.
        edited_text = f"{event.raw_text}\n\n🤖: {answer[:4000]}"
        try:
            await event.edit(edited_text)
            print(f"[VPS] ✅ edited: {answer[:80]}")
        except Exception as e:
            # Fallback to reply if edit fails
            await event.reply(answer[:4000])
            print(f"[VPS] ✅ replied (edit failed): {answer[:80]}")

    async def run(self):
        self._loop = asyncio.get_event_loop()
        await self.tg.start(phone=(self.phone or None))
        me = await self.tg.get_me()
        raw_name = getattr(me, "first_name", "?") or "?"
        base_name = re.sub(r'[𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡:]+', '', raw_name).strip()
        print(f"[VPS] ✅ Telegram connected as {base_name}")
        print(f"[VPS] 🟢 JARVIS online — send 'jarvis ...' or 'جارویس ...' in any chat.")

        self._loop.create_task(self._clock_loop(base_name))

        self.tg.add_event_handler(self._on_message, events.NewMessage(outgoing=True))
        await self.tg.run_until_disconnected()


def _interactive_login():
    """First-time login: creates jarvis.session via the normal Telethon prompts."""
    cfg = _load_config()
    api_id, api_hash = int(cfg.get("telegram_api_id", 0) or 0), cfg.get("telegram_api_hash", "")
    phone = cfg.get("telegram_phone", "") or input("Phone (with country code, e.g. +98...): ").strip()
    with TelegramClient(SESSION_PATH, api_id, api_hash) as client:
        client.start(phone=phone)
        me = client.loop.run_until_complete(client.get_me())
        print(f"✅ Logged in as {getattr(me, 'first_name', '?')}. Session saved to {SESSION_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Always-on JARVIS VPS brain")
    parser.add_argument("--login", action="store_true", help="Interactive first-time Telegram login")
    args = parser.parse_args()

    if args.login:
        _interactive_login()
        return

    brain = JarvisVPS()
    try:
        asyncio.run(brain.run())
    except KeyboardInterrupt:
        print("\n[VPS] 👋 Shutting down.")


if __name__ == "__main__":
    main()
