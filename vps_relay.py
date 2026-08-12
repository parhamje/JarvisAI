"""
vps_relay.py - Lightweight 24/7 VPS Telegram & Remote Gateway for Jarvis

Runs ONLY on your VPS. Listens for Telegram commands 24/7 and forwards them
to your primary Jarvis running on your local PC.
"""

import asyncio
import json
import websockets
from pathlib import Path
from telethon import TelegramClient, events

# Configuration
CONFIG_PATH = Path(__file__).parent / "config" / "api_keys.json"
SESSION_PATH = Path(__file__).parent / "jarvis"

# Default triggers
TRIGGERS = ("jarvis", "جارویس")

connected_pc = None

def load_keys():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

keys = load_keys()
api_id = keys.get("telegram_api_id")
api_hash = keys.get("telegram_api_hash")

async def ws_handler(websocket, path=None):
    global connected_pc
    connected_pc = websocket
    print("[VPS Relay] Local PC connected to VPS Gateway!")
    try:
        async for message in websocket:
            # Receive results from local PC and forward back if needed
            data = json.loads(message)
            print(f"[VPS Relay] Result from PC: {data.get('type')}")
    except websockets.exceptions.ConnectionClosed:
        print("[VPS Relay] Local PC disconnected.")
    finally:
        if connected_pc == websocket:
            connected_pc = None

async def start_telegram_listener():
    if not api_id or not api_hash:
        print("[VPS Relay] Error: telegram_api_id / api_hash missing in config/api_keys.json")
        return

    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.start()
    print("[VPS Relay] 24/7 Telegram Userbot active on VPS!")

    @client.on(events.NewMessage(outgoing=True))
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

        print(f"[VPS Relay] Remote Telegram Command Received: {cmd!r}")

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
            print("[VPS Relay] Command forwarded to your local PC.")
        else:
            await event.reply("⚠️ Your local PC Jarvis is currently offline, sir.")

    await client.run_until_disconnected()

async def main():
    server = await websockets.serve(ws_handler, "0.0.0.0", 8765)
    print("[VPS Relay] WebSocket Gateway listening on port 8765...")
    await asyncio.gather(
        server.wait_closed(),
        start_telegram_listener()
    )

if __name__ == "__main__":
    asyncio.run(main())
