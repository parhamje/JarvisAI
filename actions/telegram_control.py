"""
telegram_control.py — Jarvis Full Telegram Account Control (Userbot)
Uses Telethon (MTProto) to operate Parham's real Telegram account.
Session is saved to jarvis.session — authenticate once, works forever.
"""

import asyncio
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Telethon imports ─────────────────────────────────────────────────────────
try:
    from telethon import TelegramClient, functions, types as tl_types
    from telethon.errors import (
        SessionPasswordNeededError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        FloodWaitError,
    )
    from telethon.tl.functions.contacts import SearchRequest
    _TELETHON = True
except ImportError:
    _TELETHON = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_config() -> dict:
    try:
        return json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(updates: dict) -> None:
    cfg_path = _base_dir() / "config" / "api_keys.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg.update(updates)
        cfg_path.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[TelegramControl] ⚠️ Could not save config: {e}")


# ── Background event loop (keeps Telethon alive) ─────────────────────────────

_tg_loop: Optional[asyncio.AbstractEventLoop] = None
_tg_thread: Optional[threading.Thread] = None
_client: Optional["TelegramClient"] = None
_client_lock = threading.Lock()

# Auth state (persists across two calls: request_code → verify_code)
_pending_phone: Optional[str] = None
_pending_hash: Optional[str] = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _tg_loop, _tg_thread
    if _tg_loop is None or not _tg_loop.is_running():
        _tg_loop = asyncio.new_event_loop()
        _tg_thread = threading.Thread(target=_tg_loop.run_forever, daemon=True, name="TelegramLoop")
        _tg_thread.start()
    return _tg_loop


def _run(coro, timeout: int = 30):
    """Run a Telethon coroutine from a sync context."""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


def _get_client() -> "TelegramClient":
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        cfg = _get_config()
        api_id   = int(cfg.get("telegram_api_id", 0))
        api_hash = cfg.get("telegram_api_hash", "")
        session  = str(_base_dir() / "jarvis.session")

        loop = _ensure_loop()
        _client = TelegramClient(session, api_id, api_hash, loop=loop)
        return _client


def _is_connected() -> bool:
    try:
        return _run(_get_client().get_me()) is not None
    except Exception:
        return False


def get_client_and_loop():
    """Expose the shared Telethon client + its background event loop.

    Used by the inbound Telegram bridge (telegram_bridge.py) so it can register
    event handlers on the SAME client/loop the userbot already runs on, instead
    of spinning up a second connection.
    """
    return _get_client(), _ensure_loop()


# ── Entity resolution ─────────────────────────────────────────────────────────

async def _resolve_entity_async(client: "TelegramClient", target: str):
    """
    Try to resolve target to a Telegram entity.
    target can be: username (@someone), phone (+989...), display name, or 'me'/'saved'
    """
    target = target.strip()
    if not target or target.lower() in {"me", "saved messages", "myself", "parham"}:
        return "me"

    # Try direct lookup first
    try:
        return await client.get_entity(target)
    except Exception:
        pass

    # Try searching contacts by name
    try:
        contacts = await client.get_contacts()
        name_lower = target.lower()
        for c in contacts:
            full = f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip().lower()
            if name_lower in full or full in name_lower:
                return c
    except Exception:
        pass

    # Try global search
    try:
        result = await client(SearchRequest(q=target, limit=5))
        if result.users:
            return result.users[0]
    except Exception:
        pass

    raise ValueError(f"Could not find Telegram user/chat: '{target}'")


def _fmt_msg(msg) -> str:
    """Format a Telethon message object into a readable string."""
    if not msg:
        return ""
    try:
        sender = ""
        if hasattr(msg, "sender") and msg.sender:
            s = msg.sender
            sender = getattr(s, "first_name", "") or getattr(s, "title", "") or "Unknown"

        ts = ""
        if hasattr(msg, "date") and msg.date:
            local_ts = msg.date.replace(tzinfo=timezone.utc).astimezone()
            ts = local_ts.strftime("%b %d %H:%M")

        text = getattr(msg, "text", "") or "[media]"
        return f"[{ts}] {sender}: {text}"
    except Exception:
        return str(msg)


# ── Main action handler ───────────────────────────────────────────────────────

def telegram_control(parameters: dict, player=None, speak=None) -> str:
    """
    Jarvis tool entry point for full Telegram account control.

    Actions:
      login          — start login (sends OTP to phone)
      verify_code    — complete login by submitting the OTP code
      enter_password — submit 2FA password if required
      set_phone      — save your phone number to config
      send_message   — send a message to any contact/group/channel
      read_messages  — read last N messages from a chat
      get_chats      — list recent conversations
      get_unread     — fetch all chats with unread messages
      mark_as_read   — mark a chat as fully read
      send_file      — send a file or photo
      delete_message — delete a message by ID
      search         — search messages globally or in a chat
      get_me         — show your own account info
      get_contacts   — list all contacts
      logout         — log out and delete session
    """
    if not _TELETHON:
        return (
            "Telethon is not installed, Sir. "
            "Run: .venv\\Scripts\\pip install telethon"
        )

    params = parameters or {}
    action = params.get("action", "send_message").strip().lower()
    global _pending_phone, _pending_hash

    def _log(msg: str):
        print(f"[TelegramControl] {msg}")
        if player:
            player.write_log(f"[telegram] {msg}")

    # ── set_phone ─────────────────────────────────────────────────────────────
    if action == "set_phone":
        phone = params.get("phone", "").strip()
        if not phone:
            return "Please provide your phone number with country code, Sir. Example: +989123456789"
        _save_config({"telegram_phone": phone})
        _log(f"✅ Phone saved: {phone}")
        return f"Phone number saved as {phone}, Sir."

    # ── login (request OTP) ───────────────────────────────────────────────────
    if action == "login":
        global _pending_phone, _pending_hash
        phone = params.get("phone") or _get_config().get("telegram_phone", "").strip()
        if not phone:
            return (
                "I need your phone number to log in, Sir. "
                "Please tell me: 'Set my Telegram phone to +989XXXXXXXXX' first."
            )
        try:
            client = _get_client()
            _run(client.connect())
            already = _run(client.is_user_authorized())
            if already:
                me = _run(client.get_me())
                name = getattr(me, "first_name", "Unknown")
                _log(f"✅ Already logged in as {name}")
                return f"Already logged in as {name}, Sir. No action needed."

            result = _run(client.send_code_request(phone))
            _pending_phone = phone
            _pending_hash  = result.phone_code_hash
            _log(f"📱 OTP sent to {phone}")
            return (
                f"I've sent a verification code to {phone}, Sir. "
                "Please type the code you received and say: "
                "'Verify Telegram code 12345' (replace with your actual code)."
            )
        except FloodWaitError as e:
            return f"Telegram rate limit: please wait {e.seconds} seconds, Sir."
        except Exception as e:
            return f"Login failed: {e}"

    # ── verify_code (submit OTP) ──────────────────────────────────────────────
    if action == "verify_code":
        code = str(params.get("code", "")).strip().replace(" ", "")
        if not code:
            return "Please provide the verification code, Sir."
        if not _pending_phone or not _pending_hash:
            return "No pending login, Sir. Please say 'Login to Telegram' first."
        try:
            client = _get_client()
            _run(client.sign_in(phone=_pending_phone, code=code, phone_code_hash=_pending_hash))
            me = _run(client.get_me())
            name = getattr(me, "first_name", "")
            _pending_phone = None
            _pending_hash  = None
            _log(f"✅ Logged in as {name}")
            return f"Successfully logged into Telegram as {name}, Sir. I now have full access to your account."
        except PhoneCodeInvalidError:
            return "That code is incorrect, Sir. Please check the code and try again."
        except PhoneCodeExpiredError:
            return "That code has expired, Sir. Please say 'Login to Telegram' again to get a new code."
        except SessionPasswordNeededError:
            return (
                "Two-factor authentication is enabled, Sir. "
                "Please say: 'Enter Telegram password YOUR_2FA_PASSWORD'."
            )
        except Exception as e:
            return f"Verification failed: {e}"

    # ── enter_password (2FA) ──────────────────────────────────────────────────
    if action == "enter_password":
        password = params.get("password", "").strip()
        if not password:
            return "Please provide your 2FA password, Sir."
        try:
            client = _get_client()
            _run(client.sign_in(password=password))
            me = _run(client.get_me())
            name = getattr(me, "first_name", "")
            _log(f"✅ Logged in via 2FA as {name}")
            return f"2FA verified. Logged in as {name}, Sir."
        except Exception as e:
            return f"2FA login failed: {e}"

    # ── All actions below require being logged in ─────────────────────────────
    try:
        client = _get_client()
        _run(client.connect())
        authorized = _run(client.is_user_authorized())
        if not authorized:
            return (
                "I'm not logged into Telegram yet, Sir. "
                "Please say 'Login to Telegram' and provide your phone number first."
            )
    except Exception as e:
        return f"Could not connect to Telegram: {e}"

    # ── get_me ────────────────────────────────────────────────────────────────
    if action == "get_me":
        try:
            me = _run(client.get_me())
            name  = f"{getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip()
            uname = getattr(me, "username", "none")
            phone = getattr(me, "phone", "hidden")
            _log(f"✅ Me: {name} @{uname}")
            return f"Logged in as {name} (@{uname}), phone: +{phone}, Sir."
        except Exception as e:
            return f"Failed to get account info: {e}"

    # ── get_contacts ──────────────────────────────────────────────────────────
    if action == "get_contacts":
        try:
            contacts = _run(client.get_contacts())
            if not contacts:
                return "No contacts found, Sir."
            lines = []
            for c in contacts[:20]:
                name  = f"{getattr(c, 'first_name', '')} {getattr(c, 'last_name', '')}".strip()
                uname = getattr(c, "username", "")
                entry = name
                if uname:
                    entry += f" (@{uname})"
                lines.append(entry)
            total = len(contacts)
            _log(f"✅ Got {total} contacts")
            return f"Your Telegram contacts (showing up to 20 of {total}):\n" + "\n".join(lines)
        except Exception as e:
            return f"Failed to get contacts: {e}"

    # ── get_chats ─────────────────────────────────────────────────────────────
    if action == "get_chats":
        limit = int(params.get("limit", 15))
        try:
            lines = []
            dialogs = _run(client.get_dialogs(limit=limit))
            for d in dialogs:
                name    = getattr(d.entity, "title", None) or \
                          f"{getattr(d.entity, 'first_name', '')} {getattr(d.entity, 'last_name', '')}".strip()
                unread  = d.unread_count
                preview = (d.message.text[:40] + "…") if d.message and d.message.text else "[media]"
                flag    = f" 🔴{unread}" if unread else ""
                lines.append(f"• {name}{flag} — {preview}")
            _log(f"✅ Got {len(lines)} chats")
            return "Your recent Telegram chats:\n" + "\n".join(lines)
        except Exception as e:
            return f"Failed to get chats: {e}"

    # ── get_unread ────────────────────────────────────────────────────────────
    if action == "get_unread":
        try:
            dialogs = _run(client.get_dialogs(limit=50))
            unread_dialogs = [d for d in dialogs if d.unread_count > 0]
            if not unread_dialogs:
                return "You have no unread messages, Sir."
            lines = []
            for d in unread_dialogs[:10]:
                name   = getattr(d.entity, "title", None) or \
                         f"{getattr(d.entity, 'first_name', '')} {getattr(d.entity, 'last_name', '')}".strip()
                count  = d.unread_count
                preview = (d.message.text[:50] + "…") if d.message and d.message.text else "[media]"
                lines.append(f"• {name} ({count} unread) — {preview}")
            total = sum(d.unread_count for d in unread_dialogs)
            _log(f"✅ {total} unread across {len(unread_dialogs)} chats")
            return f"You have {total} unread messages across {len(unread_dialogs)} chats, Sir:\n" + "\n".join(lines)
        except Exception as e:
            return f"Failed to get unread messages: {e}"

    # ── send_message ──────────────────────────────────────────────────────────
    if action == "send_message":
        target = params.get("receiver", params.get("target", "")).strip()
        text   = params.get("text", params.get("message_text", "")).strip()
        if not text:
            return "Please provide a message to send, Sir."
        if not target:
            return "Please specify who to send the message to, Sir."
        try:
            entity = _run(_resolve_entity_async(client, target))
            _run(client.send_message(entity, text))
            name = target if isinstance(entity, str) else \
                   (getattr(entity, "first_name", None) or getattr(entity, "title", target))
            preview = text[:60] + ("…" if len(text) > 60 else "")
            _log(f"✅ Sent to {name}: {preview}")
            return f"Message sent to {name} on Telegram, Sir."
        except FloodWaitError as e:
            return f"Telegram rate limit: please wait {e.seconds} seconds, Sir."
        except Exception as e:
            return f"Failed to send message: {e}"

    # ── read_messages ─────────────────────────────────────────────────────────
    if action == "read_messages":
        target = params.get("chat", params.get("target", "")).strip()
        limit  = int(params.get("limit", 10))
        if not target:
            return "Please specify which chat to read, Sir."
        try:
            entity = _run(_resolve_entity_async(client, target))
            messages = _run(client.get_messages(entity, limit=limit))
            if not messages:
                return f"No messages found in {target}, Sir."
            lines = [_fmt_msg(m) for m in reversed(messages) if m.text or m.media]
            name = target if isinstance(entity, str) else \
                   (getattr(entity, "first_name", None) or getattr(entity, "title", target))
            _log(f"✅ Read {len(lines)} messages from {name}")
            return f"Last {len(lines)} messages from {name}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Failed to read messages: {e}"

    # ── mark_as_read ──────────────────────────────────────────────────────────
    if action == "mark_as_read":
        target = params.get("chat", params.get("target", "")).strip()
        if not target:
            return "Please specify which chat to mark as read, Sir."
        try:
            entity = _run(_resolve_entity_async(client, target))
            _run(client.send_read_acknowledge(entity))
            name = target if isinstance(entity, str) else \
                   (getattr(entity, "first_name", None) or getattr(entity, "title", target))
            _log(f"✅ Marked {name} as read")
            return f"Marked {name} as read, Sir."
        except Exception as e:
            return f"Failed to mark as read: {e}"

    # ── send_file ─────────────────────────────────────────────────────────────
    if action == "send_file":
        target    = params.get("receiver", params.get("target", "")).strip()
        file_path = params.get("file_path", "").strip()
        caption   = params.get("caption", "").strip()
        if not target:
            return "Please specify who to send the file to, Sir."
        if not file_path or not Path(file_path).exists():
            return f"File not found: {file_path}"
        try:
            entity = _run(_resolve_entity_async(client, target))
            _run(client.send_file(entity, file_path, caption=caption))
            name = target if isinstance(entity, str) else \
                   (getattr(entity, "first_name", None) or getattr(entity, "title", target))
            _log(f"✅ File sent to {name}")
            return f"File sent to {name} on Telegram, Sir."
        except Exception as e:
            return f"Failed to send file: {e}"

    # ── delete_message ────────────────────────────────────────────────────────
    if action == "delete_message":
        target  = params.get("chat", params.get("target", "")).strip()
        msg_id  = params.get("message_id")
        if not target or not msg_id:
            return "Please specify both the chat and message ID, Sir."
        try:
            entity = _run(_resolve_entity_async(client, target))
            _run(client.delete_messages(entity, [int(msg_id)]))
            _log(f"✅ Deleted message {msg_id} in {target}")
            return f"Message {msg_id} deleted, Sir."
        except Exception as e:
            return f"Failed to delete message: {e}"

    # ── search ────────────────────────────────────────────────────────────────
    if action == "search":
        query  = params.get("query", "").strip()
        target = params.get("chat", "").strip()
        limit  = int(params.get("limit", 10))
        if not query:
            return "Please provide a search query, Sir."
        try:
            if target:
                entity   = _run(_resolve_entity_async(client, target))
                messages = _run(client.get_messages(entity, search=query, limit=limit))
            else:
                messages = _run(client.get_messages(None, search=query, limit=limit))
            if not messages:
                return f"No messages found for '{query}', Sir."
            lines = [_fmt_msg(m) for m in messages if m.text]
            _log(f"✅ Found {len(lines)} messages for '{query}'")
            return f"Search results for '{query}':\n" + "\n".join(lines)
        except Exception as e:
            return f"Search failed: {e}"

    # ── logout ────────────────────────────────────────────────────────────────
    if action == "logout":
        try:
            _run(client.log_out())
            session_file = _base_dir() / "jarvis.session"
            if session_file.exists():
                session_file.unlink()
            _log("✅ Logged out")
            return "Logged out of Telegram, Sir. The session has been deleted."
        except Exception as e:
            return f"Logout failed: {e}"

    return (
        f"Unknown Telegram action: '{action}'. "
        "Supported: login, verify_code, enter_password, set_phone, send_message, "
        "read_messages, get_chats, get_unread, mark_as_read, send_file, "
        "delete_message, search, get_me, get_contacts, logout."
    )
