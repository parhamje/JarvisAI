"""
login_telegram.py — One-click Telegram Login Helper for JARVIS

Run this script to authenticate your Telegram account locally and create/renew jarvis.session:
    python login_telegram.py
"""

import asyncio
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
SESSION_PATH = BASE_DIR / "jarvis.session"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found!")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

async def main():
    try:
        from telethon import TelegramClient
    except ImportError:
        print("Telethon is not installed! Run: pip install telethon")
        sys.exit(1)

    cfg = load_config()
    api_id = int(cfg.get("telegram_api_id", 0))
    api_hash = cfg.get("telegram_api_hash", "")
    phone = cfg.get("telegram_phone", "")

    if not api_id or not api_hash:
        print("Error: telegram_api_id or telegram_api_hash is missing in config/api_keys.json!")
        sys.exit(1)

    print("=" * 60)
    print("J.A.R.V.I.S Telegram Authentication Helper")
    print("=" * 60)
    print(f"Using API ID: {api_id}")
    print(f"Session destination: {SESSION_PATH}")
    print("-" * 60)

    session_file = str(BASE_DIR / "jarvis")
    client = TelegramClient(session_file, api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already logged in as: {me.first_name} (@{me.username or 'No username'}) [ID: {me.id}]")
        print("Your jarvis.session is valid and ready!")
        await client.disconnect()
        return

    print(f"Logging in with phone number: {phone or 'Manual entry'}...")
    await client.start(phone=lambda: phone or input("Enter your Telegram phone number (with country code): "))
    me = await client.get_me()
    print("=" * 60)
    print(f"Successfully logged in as: {me.first_name} (@{me.username or 'No username'}) [ID: {me.id}]")
    print(f"Created valid session at: {SESSION_PATH}")
    print("=" * 60)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
