"""
vps_relay.py - 24/7 Hybrid Telegram Self-Bot & Gateway for Jarvis

Runs 24/7 on your VPS. Features:
1. Dynamic Profile Clock (Updates profile name every minute: PARHAM 19:55)
2. Standalone Gemini AI (Answers questions 24/7 even when your PC is turned OFF)
3. Smart PC Gateway (Relays commands to local PC when PC is turned ON)
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
import websockets
import pytz
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from google import genai

# Configuration
CONFIG_PATH = Path(__file__).parent / "config" / "api_keys.json"
SESSION_PATH = Path(__file__).parent / "jarvis"

# Default triggers
TRIGGERS = ("jarvis", "جارویس")

connected_pc = None
tg_client = None

def load_keys():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

keys = load_keys()
api_id = keys.get("telegram_api_id")
api_hash = keys.get("telegram_api_hash")
gemini_key = keys.get("gemini_api_key")

# Initialize Gemini AI Client for VPS fallback
ai_client = None
if gemini_key:
    try:
        ai_client = genai.Client(api_key=gemini_key)
        print("[VPS Relay] Gemini 24/7 AI Engine ready.")
    except Exception as e:
        print(f"[VPS Relay] Gemini AI init warning: {e}")

async def ws_handler(websocket, path=None):
    global connected_pc
    connected_pc = websocket
    print("[VPS Relay] ✅ Local PC connected to VPS Gateway!")
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            print(f"[VPS Relay] Message from PC: {msg_type}")
            if msg_type == "TELEGRAM_REPLY" and tg_client:
                payload = data.get("payload", {})
                chat_id = payload.get("chat_id")
                reply_text = payload.get("text", "")
                if chat_id and reply_text:
                    await tg_client.send_message(chat_id, reply_text)
                    print(f"[VPS Relay] Relayed reply to Telegram chat {chat_id}")
    except websockets.exceptions.ConnectionClosed:
        print("[VPS Relay] Local PC disconnected.")
    finally:
        if connected_pc == websocket:
            connected_pc = None

async def clock_loop():
    """24/7 Dynamic Profile Clock Update"""
    if not tg_client:
        return
    tz = pytz.timezone("Asia/Tehran")
    digits = {'0': '𝟘', '1': '𝟙', '2': '𝟚', '3': '𝟛', '4': '𝟜', 
              '5': '𝟝', '6': '𝟞', '7': '𝟟', '8': '𝟠', '9': '𝟡', ':': ':'}
    
    while True:
        try:
            me = await tg_client.get_me()
            raw_name = getattr(me, "first_name", "PARHAM") or "PARHAM"
            base_name = re.sub(r'[𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡:]+', '', raw_name).strip() or "PARHAM"

            now = datetime.now(tz)
            time_str = now.strftime("%H:%M")
            styled_time = "".join(digits.get(c, c) for c in time_str)
            new_name = f"{base_name} {styled_time}".strip()

            if raw_name != new_name:
                await tg_client(UpdateProfileRequest(first_name=new_name))
        except Exception as e:
            print(f"[VPS Relay] Clock update: {e}")
        await asyncio.sleep(60)

async def generate_vps_ai_reply(prompt: str) -> str:
    """Generate Gemini AI response when local PC is offline"""
    if not ai_client:
        return "I am Jarvis AI. My local PC host is currently offline, sir."
    try:
        loop = asyncio.get_running_loop()
        system_instruction = (
            "You are J.A.R.V.I.S., a highly intelligent, polite, futuristic AI assistant created by Parham. "
            "Respond concisely and helpfully in English or Persian based on the user's input language."
        )
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"system_instruction": system_instruction}
            )
        )
        return response.text
    except Exception as e:
        return f"Error processing AI request on VPS: {e}"

async def start_telegram_listener():
    global tg_client
    if not api_id or not api_hash:
        print("[VPS Relay] Error: telegram_api_id / api_hash missing in config/api_keys.json")
        return

    tg_client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await tg_client.start()
    print("[VPS Relay] 24/7 Telegram Self-Bot active on VPS!")

    # Start 24/7 profile clock loop
    asyncio.create_task(clock_loop())

    @tg_client.on(events.NewMessage(outgoing=True))
    async def handler(event):
        text = (event.raw_text or "").strip()
        if not text:
            return
            
        lower_text = text.lower()
        matched_trigger = None
        for t in TRIGGERS:
            if lower_text.startswith(t):
                matched_trigger = t
                break
                
        if not matched_trigger:
            return

        cmd = text[len(matched_trigger):].strip()
        if not cmd:
            return

        print(f"[VPS Relay] Remote Command: {cmd!r}")

        if connected_pc:
            # Forward command to local PC
            await connected_pc.send(json.dumps({
                "type": "TELEGRAM_REMOTE_CMD",
                "payload": {
                    "cmd": cmd,
                    "chat_id": event.chat_id,
                    "msg_id": event.id
                }
            }))
            print("[VPS Relay] Forwarded to local PC.")
        else:
            # Standalone VPS AI Response (When PC is offline)
            print("[VPS Relay] PC is offline. Generating standalone Gemini AI reply on VPS...")
            ai_reply = await generate_vps_ai_reply(cmd)
            await event.reply(ai_reply)

    await tg_client.run_until_disconnected()

async def main():
    server = await websockets.serve(ws_handler, "0.0.0.0", 8765)
    print("[VPS Relay] WebSocket Gateway listening on port 8765...")
    await asyncio.gather(
        server.wait_closed(),
        start_telegram_listener()
    )

if __name__ == "__main__":
    asyncio.run(main())
