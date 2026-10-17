"""
login_telegram.py — Interactive Telegram Login Helper for JARVIS (VPS & Local)
Supports:
1. QR Code Scan (Recommended — Fastest, No SMS/App code needed)
2. Phone Number with SMS/App Code Diagnostics & 2FA Password handling
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
SESSION_FILE = BASE_DIR / "jarvis"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found!")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

async def qr_login_flow(client):
    try:
        import qrcode
    except ImportError:
        print("[!] Installing 'qrcode' library for terminal QR display...")
        os.system(f"{sys.executable} -m pip install qrcode >/dev/null 2>&1")
        import qrcode

    print("\n" + "=" * 60)
    print("📲 TELEGRAM QR CODE LOGIN")
    print("=" * 60)
    print("1. Open Telegram on your phone")
    print("2. Go to: Settings (تنظیمات) -> Devices (دستگاه‌ها) -> Link Desktop Device (اتصال دستگاه)")
    print("3. Point your camera at the QR code below:")
    print("-" * 60)

    while not await client.is_user_authorized():
        qr_login = await client.qr_login()
        qr = qrcode.QRCode()
        qr.clear()
        qr.add_data(qr_login.url)
        print("\n")
        qr.print_ascii(invert=True)
        print("\n" + "-" * 60)
        print(f"🔗 Direct Link: {qr_login.url}")
        print("Waiting for you to scan... (refreshes in 30s)")

        try:
            await qr_login.wait(timeout=30)
            print("\n✅ QR Code successfully scanned and authorized!")
            break
        except asyncio.TimeoutError:
            print("[...] QR code expired. Refreshing new QR code...")
            try:
                await qr_login.recreate()
            except Exception:
                pass
        except Exception as e:
            from telethon.errors import SessionPasswordNeededError
            if isinstance(e, SessionPasswordNeededError) or "SessionPasswordNeededError" in str(type(e)):
                print("\n🔐 Two-Step Verification (2FA) is enabled on this account.")
                pwd = input("Enter your 2FA Cloud Password: ")
                await client.sign_in(password=pwd)
                print("✅ 2FA Password accepted!")
                break
            else:
                print(f"[!] Error during QR login: {e}")
                break

async def phone_login_flow(client):
    from telethon.errors import SessionPasswordNeededError

    print("\n" + "=" * 60)
    print("📱 PHONE NUMBER LOGIN")
    print("=" * 60)
    raw_phone = input("Enter your phone number (e.g. +447552734338 or +98912...): ").strip()
    # Normalize: keep only digits and leading +
    phone = "+" + re.sub(r"[^\d]", "", raw_phone) if raw_phone.startswith("+") else re.sub(r"[^\d]", "", raw_phone)
    if not phone.startswith("+"):
        phone = "+" + phone

    print(f"\n[+] Requesting login code for: {phone} ...")
    try:
        sent_code = await client.send_code_request(phone)
    except Exception as e:
        print(f"❌ Telegram Error requesting code: {e}")
        return

    code_type = type(sent_code.type).__name__
    print("\n" + "-" * 60)
    if "App" in code_type:
        print(f"📩 کد تأیید به **داخل اپلیکیشن تلگرام** در چت رسمی Telegram فرستاده شد.")
        print(f"👉 لطفاً تلگرام گوشی‌تان را باز کرده و کد را از چت Telegram بردارید.")
    elif "Sms" in code_type:
        print(f"📱 کد تأیید به صورت **پیامک (SMS)** به سیم‌کارت {phone} ارسال شد.")
        print(f"👉 اگر این شماره سیم‌کارت فیزیکی در دسترس شما نیست، از روش اسکن QR Code استفاده کنید.")
    elif "Call" in code_type:
        print(f"📞 تلگرام با شماره {phone} تماس صوتی می‌گیرد.")
    else:
        print(f"ℹ️ نوع ارسال کد: {code_type}")
    print("-" * 60)

    code = input("\nEnter the 5-digit code you received: ").strip()
    # Remove any spaces in code
    code = re.sub(r"[^\d]", "", code)

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=sent_code.phone_code_hash)
        print("✅ Logged in successfully!")
    except SessionPasswordNeededError:
        print("\n🔐 Two-Step Verification (2FA) is enabled on this account.")
        pwd = input("Enter your 2FA Cloud Password: ")
        await client.sign_in(password=pwd)
        print("✅ 2FA Password accepted!")
    except Exception as e:
        print(f"❌ Login error: {e}")

async def main():
    try:
        from telethon import TelegramClient
    except ImportError:
        print("Telethon not installed!")
        sys.exit(1)

    cfg = load_config()
    api_id = int(cfg.get("telegram_api_id", 0))
    api_hash = cfg.get("telegram_api_hash", "")

    if not api_id or not api_hash:
        print("Error: api_id or api_hash missing in config/api_keys.json!")
        sys.exit(1)

    client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print("=" * 60)
        print(f"✅ Already logged in as: {me.first_name} (@{me.username or 'No username'}) [ID: {me.id}]")
        print(f"Session file: {SESSION_FILE}.session")
        print("You can now start background service with: ./start_vps.sh")
        print("=" * 60)
        await client.disconnect()
        return

    print("=" * 60)
    print("🤖 JARVIS TELEGRAM AUTHENTICATION")
    print("=" * 60)
    print("Choose login method:")
    print("  [1] 📲 Scan QR Code with Telegram App (Fastest & Recommended - No SMS needed!)")
    print("  [2] 📱 Enter Phone Number (SMS / Telegram App Code)")
    choice = input("\nEnter choice (1 or 2, default is 1): ").strip()

    if choice == "2":
        await phone_login_flow(client)
    else:
        await qr_login_flow(client)

    if await client.is_user_authorized():
        me = await client.get_me()
        print("\n" + "=" * 60)
        print(f"🎉 Login Complete! Account: {me.first_name} (@{me.username or 'No username'}) [ID: {me.id}]")
        print(f"Session saved to: {SESSION_FILE}.session")
        print("Next step: Run './start_vps.sh' to activate 24/7 Jarvis daemon.")
        print("=" * 60)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
