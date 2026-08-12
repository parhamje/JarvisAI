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

GAPGPT_KEY = "sk-b4fdrNkj3xxH020rdt5OAVmOCty3rukoO6ZfMMtjQLtVXF87"
GAPGPT_URL = "https://api.gapgpt.app/v1/chat/completions"
GAPGPT_MODEL = "gapgpt-qwen-3.6-thinking"

def _gapgpt_generate(prompt: str) -> str:
    import requests
    headers = {
        "Authorization": f"Bearer {GAPGPT_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GAPGPT_MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "You are J.A.R.V.I.S., a highly intelligent, polite, futuristic AI assistant created by Parham. Respond concisely and helpfully in English or Persian based on user input language."
            },
            {"role": "user", "content": prompt}
        ]
    }
    res = requests.post(GAPGPT_URL, headers=headers, json=payload, timeout=25)
    res.raise_for_status()
    data = res.json()
    choices = data.get("choices", [])
    if choices and "message" in choices[0]:
        return choices[0]["message"].get("content", "").strip()
    raise ValueError("Invalid GapGPT response structure")

openrouter_key = keys.get("openrouter_api_key")

def _openrouter_generate(prompt: str) -> str:
    import requests
    if not openrouter_key:
        raise ValueError("OpenRouter API key missing")
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
    }
    
    free_models = [
        "openai/gpt-oss-20b:free",
        "nvidia/nemotron-3.5-lightning:free",
        "liquid/lfm-2.5-2.6b:free",
        "openrouter/free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free"
    ]
    
    last_err = None
    for model_name in free_models:
        try:
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are J.A.R.V.I.S., a highly intelligent, polite, futuristic AI assistant created by Parham. Respond concisely and helpfully in English or Persian based on user input language."
                    },
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=25)
            res.raise_for_status()
            data = res.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                content = choices[0]["message"].get("content", "").strip()
                if content:
                    return content
        except Exception as e:
            last_err = e
            continue

    raise last_err or Exception("All free OpenRouter models failed")

async def generate_vps_ai_reply(prompt: str) -> str:
    """Generate AI response using GapGPT -> OpenRouter -> Gemini"""
    loop = asyncio.get_running_loop()
    
    # 1. Try GapGPT (Ultra fast Iranian AI gateway, no geo-restrictions)
    try:
        reply = await loop.run_in_executor(None, _gapgpt_generate, prompt)
        if reply:
            return reply
    except Exception as e1:
        print(f"[VPS Relay] GapGPT failed ({e1}). Trying OpenRouter...")

    # 2. Try OpenRouter Free Models
    try:
        reply = await loop.run_in_executor(None, _openrouter_generate, prompt)
        if reply:
            return reply
    except Exception as e2:
        print(f"[VPS Relay] OpenRouter failed ({e2}). Trying direct Gemini...")

    # 3. Direct Gemini Fallback
    if ai_client:
        try:
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
        except Exception as e3:
            print(f"[VPS Relay] Direct Gemini failed ({e3}).")

    return "Sir, all AI engines (GapGPT, OpenRouter, Gemini) were unreachable."

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
        raw_text = (event.raw_text or "").strip()
        if not raw_text:
            return
            
        lower_text = raw_text.lower()
        matched_trigger = None
        for t in TRIGGERS:
            if t in lower_text:
                matched_trigger = t
                break
                
        if not matched_trigger:
            return

        # Extract command or default to "سلام" if only trigger is typed
        idx = lower_text.find(matched_trigger)
        cmd = raw_text[idx + len(matched_trigger):].strip()
        if not cmd:
            cmd = "سلام"

        print(f"[VPS Relay] Self-Bot Triggered: '{raw_text}' -> Command: '{cmd}'")

        if connected_pc:
            # Forward command to local PC
            try:
                await event.edit(f"{raw_text}\n\n⚡ *JARVIS (Relaying to PC...)*", parse_mode="markdown")
            except Exception:
                pass
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
            # Standalone VPS AI Response (Self-Bot In-Place Editing)
            try:
                await event.edit(f"{raw_text}\n\n🧠 *thinking...*", parse_mode="markdown")
            except Exception:
                pass
                
            print("[VPS Relay] PC is offline. Generating standalone AI reply on VPS...")
            ai_reply = await generate_vps_ai_reply(cmd)

            # Edit message in-place with final AI answer
            try:
                await event.edit(f"{raw_text}\n\n🤖 **J.A.R.V.I.S:**\n{ai_reply}", parse_mode="markdown")
            except Exception:
                await event.edit(f"{raw_text}\n\n🤖 J.A.R.V.I.S:\n{ai_reply}")

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
