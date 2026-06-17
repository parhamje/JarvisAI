"""
telegram_bot.py — Jarvis Telegram Bot Integration
Uses the official Telegram Bot API to send messages, photos, and files.
Supports sending to any chat/user by username, chat ID, or saved contacts.
"""

import json
import sys
import threading
import time
from pathlib import Path
from typing import Optional

try:
    import requests as _requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_config() -> dict:
    try:
        cfg_path = _base_dir() / "config" / "api_keys.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_bot_token() -> str:
    return _get_config().get("telegram_bot_token", "").strip()


def _get_default_chat_id() -> str:
    return _get_config().get("telegram_chat_id", "").strip()


def _save_config_field(key: str, value: str) -> None:
    """Persist a key back to api_keys.json."""
    cfg_path = _base_dir() / "config" / "api_keys.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg[key] = value
        cfg_path.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[TelegramBot] ⚠️ Could not save config: {e}")


# ──────────────────────────────────────────────
# Low-level API helpers
# ──────────────────────────────────────────────

def _api(token: str, method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method. Returns the JSON response dict."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        resp = _requests.post(url, timeout=15, **kwargs)
        return resp.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _resolve_chat_id(token: str, receiver: str) -> Optional[str]:
    """
    Try to find the chat_id for a given receiver.
    receiver can be:
      - a numeric chat ID  (e.g. "123456789")
      - a @username        (e.g. "@parham" or "parham")
      - "me" / "parham"   → uses the saved default chat_id
    """
    receiver = receiver.strip()

    # Numeric ID — use as-is
    if receiver.lstrip("-").isdigit():
        return receiver

    # "me" or the user's own name → use saved default
    lower = receiver.lower()
    if lower in {"me", "myself", "parham", "sir"}:
        cid = _get_default_chat_id()
        if cid:
            return cid

    # @username — Telegram bots can only message users who have
    # already started the bot. We scan recent updates for the username.
    username = receiver.lstrip("@").lower()
    result = _api(token, "getUpdates", json={"limit": 100, "offset": -100})
    if result.get("ok"):
        for update in result.get("result", []):
            for key in ("message", "edited_message", "channel_post"):
                msg = update.get(key, {})
                chat = msg.get("chat", {})
                frm  = msg.get("from", {})
                uname = (frm.get("username") or chat.get("username") or "").lower()
                if uname == username:
                    return str(chat["id"])

    return None


# ──────────────────────────────────────────────
# Public-facing action handler
# ──────────────────────────────────────────────

def telegram_bot(parameters: dict, player=None, speak=None) -> str:
    """
    Main entry point called by main.py.

    Supported actions:
      send_message   — send a text message
      send_photo     — send an image file
      send_file      — send any document/file
      get_me         — get bot info
      get_updates    — fetch recent messages received by the bot
      set_token      — save a new bot token to config
      set_chat_id    — save a default chat ID to config
      setup          — interactive setup wizard (for first-time config)
    """
    if not _REQUESTS:
        return "The 'requests' library is not installed. Run: pip install requests"

    params  = parameters or {}
    action  = params.get("action", "send_message").strip().lower()
    token   = params.get("token") or _get_bot_token()

    def _log(msg: str):
        print(f"[TelegramBot] {msg}")
        if player:
            player.write_log(f"[telegram] {msg}")

    # ── setup / token management ──────────────────────────────────────
    if action == "set_token":
        new_token = params.get("token", "").strip()
        if not new_token:
            return "Please provide a bot token."
        _save_config_field("telegram_bot_token", new_token)
        _log(f"✅ Bot token saved.")
        return "Telegram bot token saved successfully, Sir."

    if action == "set_chat_id":
        cid = params.get("chat_id", "").strip()
        if not cid:
            return "Please provide a chat ID."
        _save_config_field("telegram_chat_id", cid)
        _log(f"✅ Default chat ID saved: {cid}")
        return f"Default Telegram chat ID set to {cid}, Sir."

    if action == "setup":
        return (
            "To set up Telegram, Sir, please:\n"
            "1. Open Telegram and search for @BotFather.\n"
            "2. Send /newbot and follow instructions to get your bot token.\n"
            "3. Tell me: 'Set my Telegram bot token to <token>'\n"
            "4. Start a chat with your bot, then tell me: 'Get my Telegram chat ID'\n"
            "5. Tell me: 'Set my Telegram chat ID to <id>'"
        )

    if not token:
        return (
            "Telegram bot token is not configured, Sir. "
            "Please tell me: 'Set my Telegram bot token to <your_token>' to get started."
        )

    # ── get_me ───────────────────────────────────────────────────────
    if action == "get_me":
        result = _api(token, "getMe")
        if result.get("ok"):
            bot = result["result"]
            return f"Bot name: {bot.get('first_name')}, username: @{bot.get('username')}"
        return f"Failed to get bot info: {result.get('description', 'Unknown error')}"

    # ── get_updates (read incoming messages) ─────────────────────────
    if action == "get_updates":
        result = _api(token, "getUpdates", json={"limit": 10, "offset": -10})
        if not result.get("ok"):
            return f"Failed to get updates: {result.get('description', 'Unknown error')}"
        updates = result.get("result", [])
        if not updates:
            return "No recent messages found."
        lines = []
        for upd in updates[-5:]:
            msg  = upd.get("message") or upd.get("edited_message") or {}
            frm  = msg.get("from", {})
            name = frm.get("first_name", "Unknown")
            text = msg.get("text", "[non-text]")
            lines.append(f"{name}: {text}")
        return "Recent Telegram messages:\n" + "\n".join(lines)

    # ── get_chat_id helper ────────────────────────────────────────────
    if action == "get_chat_id":
        result = _api(token, "getUpdates", json={"limit": 100, "offset": -100})
        if not result.get("ok"):
            return f"Failed: {result.get('description', 'Unknown error')}"
        updates = result.get("result", [])
        if not updates:
            return (
                "No messages received yet. Please send any message to your bot first, "
                "then ask me again."
            )
        # Return unique chat IDs
        seen = {}
        for upd in updates:
            msg  = upd.get("message") or {}
            chat = msg.get("chat", {})
            frm  = msg.get("from", {})
            cid  = str(chat.get("id", ""))
            name = frm.get("first_name", "") + " " + frm.get("last_name", "")
            uname = frm.get("username", "")
            if cid:
                seen[cid] = f"{name.strip()} (@{uname}) — chat ID: {cid}"
        if not seen:
            return "Could not extract any chat IDs from recent updates."
        lines = list(seen.values())
        # Auto-save if only one user found
        if len(lines) == 1:
            cid = list(seen.keys())[0]
            _save_config_field("telegram_chat_id", cid)
            _log(f"✅ Auto-saved chat ID: {cid}")
            return f"Your Telegram chat ID is {cid}. I've saved it automatically, Sir."
        return "Found these chats:\n" + "\n".join(lines)

    # ── send_message ──────────────────────────────────────────────────
    if action == "send_message":
        receiver = params.get("receiver", "").strip()
        text     = params.get("text", params.get("message_text", "")).strip()
        if not text:
            return "Please provide a message to send, Sir."

        # Resolve chat ID
        if receiver:
            chat_id = _resolve_chat_id(token, receiver)
        else:
            chat_id = _get_default_chat_id()

        if not chat_id:
            return (
                f"Could not find Telegram chat ID for '{receiver}'. "
                "Make sure they have messaged your bot first, or set a default chat ID."
            )

        result = _api(token, "sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })

        if result.get("ok"):
            preview = text[:60] + ("…" if len(text) > 60 else "")
            _log(f"✅ Sent to {chat_id}: {preview}")
            return f"Message sent via Telegram, Sir."
        else:
            err = result.get("description", "Unknown error")
            _log(f"❌ Send failed: {err}")
            return f"Telegram send failed: {err}"

    # ── send_photo ────────────────────────────────────────────────────
    if action == "send_photo":
        receiver  = params.get("receiver", "").strip()
        file_path = params.get("file_path", "").strip()
        caption   = params.get("caption", "").strip()

        chat_id = _resolve_chat_id(token, receiver) if receiver else _get_default_chat_id()
        if not chat_id:
            return "Could not resolve Telegram chat ID, Sir."
        if not file_path or not Path(file_path).exists():
            return f"File not found: {file_path}"

        with open(file_path, "rb") as f:
            result = _api(token, "sendPhoto",
                          data={"chat_id": chat_id, "caption": caption},
                          files={"photo": f})

        if result.get("ok"):
            _log(f"✅ Photo sent to {chat_id}")
            return "Photo sent via Telegram, Sir."
        return f"Telegram photo send failed: {result.get('description', 'Unknown error')}"

    # ── send_file ─────────────────────────────────────────────────────
    if action == "send_file":
        receiver  = params.get("receiver", "").strip()
        file_path = params.get("file_path", "").strip()
        caption   = params.get("caption", "").strip()

        chat_id = _resolve_chat_id(token, receiver) if receiver else _get_default_chat_id()
        if not chat_id:
            return "Could not resolve Telegram chat ID, Sir."
        if not file_path or not Path(file_path).exists():
            return f"File not found: {file_path}"

        with open(file_path, "rb") as f:
            result = _api(token, "sendDocument",
                          data={"chat_id": chat_id, "caption": caption},
                          files={"document": f})

        if result.get("ok"):
            _log(f"✅ File sent to {chat_id}")
            return "File sent via Telegram, Sir."
        return f"Telegram file send failed: {result.get('description', 'Unknown error')}"

    return f"Unknown Telegram action: '{action}'. Supported: send_message, send_photo, send_file, get_me, get_updates, get_chat_id, set_token, set_chat_id, setup."
