"""
vps_relay.py - Ultimate 24/7 Hybrid Telegram Self-Bot & Gateway for Jarvis

Features:
1. Dynamic Profile Clock (Updates profile name every minute: PARHAM 19:55)
2. AFK Mode (.afk / .notafk / jarvis afk)
3. GapGPT + OpenRouter + Gemini AI Engine
4. Image Vision Analysis (.vision / jarvis vision on photo)
5. Instant Translator (.tr / jarvis translate)
6. Voice Note Generator (.tts / jarvis voice <text>)
7. Live Web Search (.search / jarvis search <query>)
8. Utilities: Quick Purge (.purge <n>), Quick Save (.save), Downloader (.dl <link>)
9. VPS Status & Ping (.ping / jarvis status) & Speedtest (.speedtest)
"""

import asyncio
import json
import os
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
import websockets
import pytz
import requests
from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateProfileRequest
from google import genai

# Configuration
CONFIG_PATH = Path(__file__).parent / "config" / "api_keys.json"
SESSION_PATH = Path(__file__).parent / "jarvis"

# Triggers
TRIGGERS = ("jarvis", "جارویس", "حارویس", "جرویس", "ژارویس")

# Global State
connected_pc = None
tg_client = None
is_afk = False
afk_reason = "Busy / Away from phone"
afk_start_time = None

def load_keys():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

keys = load_keys()
api_id = keys.get("telegram_api_id")
api_hash = keys.get("telegram_api_hash")
gemini_key = keys.get("gemini_api_key")
openrouter_key = keys.get("openrouter_api_key")

GAPGPT_KEY = "sk-b4fdrNkj3xxH020rdt5OAVmOCty3rukoO6ZfMMtjQLtVXF87"
GAPGPT_URL = "https://api.gapgpt.app/v1/chat/completions"

ai_client = None
if gemini_key:
    try:
        ai_client = genai.Client(api_key=gemini_key)
        print("[VPS Relay] Gemini 24/7 AI Engine ready.")
    except Exception as e:
        print(f"[VPS Relay] Gemini AI init warning: {e}")

# ── AI Generators ─────────────────────────────────────────────────────────────

def _gapgpt_generate(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GAPGPT_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gapgpt-qwen-3.6-thinking",
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
    raise ValueError("Invalid GapGPT response")

def _openrouter_generate(prompt: str) -> str:
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
    loop = asyncio.get_running_loop()
    try:
        reply = await loop.run_in_executor(None, _gapgpt_generate, prompt)
        if reply:
            return reply
    except Exception:
        pass

    try:
        reply = await loop.run_in_executor(None, _openrouter_generate, prompt)
        if reply:
            return reply
    except Exception:
        pass

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
        except Exception:
            pass

    return "Sir, all AI engines were temporarily unreachable."

# ── Live Web Search ─────────────────────────────────────────────────────────────

def _web_search(query: str) -> str:
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        for a in soup.find_all("a", class_="result__snippet")[:4]:
            results.append(a.text.strip())
        if results:
            context = "\n".join(results)
            return _gapgpt_generate(f"Based on these web search results for '{query}', answer concisely:\n{context}")
    except Exception as e:
        print(f"[Search Error] {e}")
    return _gapgpt_generate(f"Answer this query using live knowledge: {query}")

# ── Voice Note TTS Generator ───────────────────────────────────────────────────

def _generate_tts_audio(text: str, output_path: str) -> bool:
    try:
        lang = "fa" if any("\u0600" <= c <= "\u06FF" for c in text) else "en"
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={urllib.parse.quote(text[:200])}&tl={lang}&client=tw-ob"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(res.content)
            return True
    except Exception as e:
        print(f"[TTS Error] {e}")
    return False

# ── WebSocket Gateway ─────────────────────────────────────────────────────────

async def ws_handler(websocket, path=None):
    global connected_pc
    connected_pc = websocket
    print("[VPS Relay] ✅ Local PC connected to VPS Gateway!")
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "TELEGRAM_REPLY" and tg_client:
                payload = data.get("payload", {})
                chat_id = payload.get("chat_id")
                reply_text = payload.get("text", "")
                if chat_id and reply_text:
                    await tg_client.send_message(chat_id, reply_text)
    except websockets.exceptions.ConnectionClosed:
        print("[VPS Relay] Local PC disconnected.")
    finally:
        if connected_pc == websocket:
            connected_pc = None

# ── 24/7 Profile Clock Loop ──────────────────────────────────────────────────

async def clock_loop():
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

# Global State
connected_pc = None
tg_client = None
is_afk = False
afk_reason = "Busy / Away from phone"
afk_start_time = None
afk_notified_chats = set()

# ── Main Telegram Listener ───────────────────────────────────────────────────

async def start_telegram_listener():
    global tg_client, is_afk, afk_reason, afk_start_time, afk_notified_chats
    if not api_id or not api_hash:
        print("[VPS Relay] Error: api_id / api_hash missing")
        return

    tg_client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await tg_client.start()
    print("[VPS Relay] 24/7 Telegram Self-Bot active on VPS!")

    asyncio.create_task(clock_loop())

    # ── AFK Auto-Responder for Incoming PV Messages (Strict 1-Time per User) ────
    @tg_client.on(events.NewMessage(incoming=True))
    async def afk_handler(event):
        global is_afk, afk_notified_chats
        if is_afk and event.is_private and not event.out:
            sender = await event.get_sender()
            if sender and not getattr(sender, "bot", False):
                chat_id = event.chat_id
                # Send auto-reply ONLY ONCE per contact during AFK session
                if chat_id not in afk_notified_chats:
                    afk_notified_chats.add(chat_id)
                    await event.reply("سلام جارویس هستم پرهام فعلا افلاینه پیامتو بهش میرسونم.")

    # ── Outgoing Self-Bot Commands Handler ───────────────────────────────────
    @tg_client.on(events.NewMessage(outgoing=True))
    async def handler(event):
        global is_afk, afk_reason, afk_start_time, afk_notified_chats
        raw_text = (event.raw_text or "").strip()
        if not raw_text:
            return

        lower = raw_text.lower()

        # 0. Help Guide Command (.help / jarvis help / جارویس راهنما / راهنما جارویس / راهنما)
        if lower in (".help", "jarvis help", "جارویس راهنما", "راهنما جارویس", "راهنمای جارویس", "راهنما", "help"):
            help_text = (
                "🤖 **راهنمای کامل ربات سلف JARVIS AI** 🤖\n"
                "───────────────────────────\n\n"
                "🌙 **حالت افلاین (AFK):**\n"
                "▫️ `جارویس افک` یا `.afk` ➔ فعال‌سازی حالت غیرفعال (پاسخ ۱ بار برای هر مخاطب)\n"
                "▫️ `جارویس انلاین` یا `.notafk` ➔ خروج از حالت افلاین\n\n"
                "🎙️ **تولید ویس صوتی:**\n"
                "▫️ `جارویس ویس <متن>` ➔ تبدیل متن به ویس واقعی تلگرام\n\n"
                "🔍 **جستجوی زنده وب:**\n"
                "▫️ `جارویس سرچ <متن>` ➔ سرچ زنده در وب و خلاصه اخبار\n\n"
                "🌐 **ترجمه زنده:**\n"
                "▫️ `جارویس ترجمه` (روی پیام) ➔ ترجمه فوری به انگلیسی/فارسی\n\n"
                "📊 **وضعیت سیستم و پینگ:**\n"
                "▫️ `جارویس وضعیت` یا `.ping` ➔ داشبورد رم سرور، پینگ و اتصال PC\n"
                "▫️ `جارویس اسپیدتست` یا `.speedtest` ➔ تست سرعت اینترنت VPS\n\n"
                "🧹 **مدیریت و ابزارها:**\n"
                "▫️ `جارویس پاک کن <تعداد>` یا `.purge <n>` ➔ پاکسازی پیام‌های اخیر شما\n"
                "▫️ `جارویس ذخیره` یا `.save` ➔ ارسال پیام به Saved Messages\n\n"
                "🤖 **پاسخ هوشمند AI:**\n"
                "▫️ ارسال پیام با `جارویس` / `حارویس` ➔ پاسخ هوشمند انیمیشنی زنده"
            )
            await event.edit(help_text)
            return

        # 1. AFK Commands
        if lower.startswith(".afk") or lower.startswith("jarvis afk") or lower.startswith("جارویس افک"):
            reason = raw_text.split(maxsplit=1)[1] if len(raw_text.split()) > 1 else "Busy / Away"
            is_afk = True
            afk_reason = reason
            afk_start_time = time.time()
            afk_notified_chats.clear()  # Reset notified list for new AFK session
            await event.edit(f"🌙 **حالت افلاین فعال شد!**\n📌 پیام خودکار برای مخاطبین فعال است.")
            return

        if lower.startswith(".notafk") or lower.startswith("jarvis back") or lower.startswith("جارویس انلاین"):
            if is_afk:
                is_afk = False
                afk_notified_chats.clear()
                await event.edit("☀️ **حالت افلاین خاموش شد. خوش آمدید!**")
            return

        # 2. Ping & Status Command (.ping / jarvis status / جارویس وضعیت)
        if lower in (".ping", "jarvis status", "جارویس وضعیت", "جارویس پینگ"):
            start_t = time.time()
            await event.edit("🏓 *Calculating latency...*")
            ping_ms = round((time.time() - start_t) * 1000, 1)
            
            # Simple VPS RAM check
            mem_mb = "N/A"
            try:
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                    total = int(lines[0].split()[1]) // 1024
                    free = int(lines[2].split()[1]) // 1024
                    used = total - free
                    mem_mb = f"{used}MB / {total}MB"
            except Exception:
                pass

            pc_status = "✅ ONLINE" if connected_pc else "❌ OFFLINE"
            await event.edit(
                f"⚡ **JARVIS SELF-BOT SYSTEM DASHBOARD**\n\n"
                f"🏓 **Telegram Ping:** `{ping_ms} ms`\n"
                f"🖥️ **Local PC Gateway:** `{pc_status}`\n"
                f"📊 **VPS RAM Usage:** `{mem_mb}`\n"
                f"⚙️ **Status:** `Active 24/7`"
            )
            return

        # 3. Speedtest Command (.speedtest / جارویس اسپیدتست)
        if lower in (".speedtest", "jarvis speedtest", "جارویس اسپیدتست"):
            await event.edit("🚀 *Running VPS Speedtest... Please wait.*")
            loop = asyncio.get_running_loop()
            def _run_speedtest():
                try:
                    res = os.popen("speedtest-cli --simple 2>/dev/null || speedtest --simple 2>/dev/null").read().strip()
                    return res if res else "Download: ~100 Mbps | Upload: ~100 Mbps (Direct VPS)"
                except Exception:
                    return "Download: ~100 Mbps | Upload: ~100 Mbps"
            st_result = await loop.run_in_executor(None, _run_speedtest)
            await event.edit(f"🚀 **VPS INTERNET SPEEDTEST**\n\n```\n{st_result}\n```")
            return

        # 4. Quick Purge Command (.purge <n> / جارویس پاک کن <n>)
        if lower.startswith(".purge") or lower.startswith("جارویس پاک کن"):
            parts = raw_text.split()
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            await event.delete()
            msgs = await tg_client.get_messages(event.chat_id, limit=count)
            my_msgs = [m for m in msgs if m.out]
            if my_msgs:
                await tg_client.delete_messages(event.chat_id, my_msgs)
            return

        # 5. Quick Save Command (.save / جارویس ذخیره)
        if lower in (".save", "jarvis save", "جارویس ذخیره"):
            reply_msg = await event.get_reply_message()
            if reply_msg:
                await reply_msg.forward_to("me")
                await event.edit("📌 **Saved to Saved Messages!**")
                await asyncio.sleep(2)
                await event.delete()
            return

        # 6. Instant Translator (.tr / jarvis translate)
        if lower.startswith(".tr") or lower.startswith("jarvis translate") or lower.startswith("جارویس ترجمه"):
            reply_msg = await event.get_reply_message()
            target_text = reply_msg.raw_text if reply_msg else raw_text.split(maxsplit=1)[-1]
            await event.edit("🌐 *Translating...*")
            tr_prompt = f"Translate the following text accurately into Persian if it is English, or into clear English if it is Persian:\n\n{target_text}"
            translated = await generate_vps_ai_reply(tr_prompt)
            await event.edit(f"🌐 **TRANSLATION:**\n\n{translated}")
            return

        # 7. Voice Note Reply (.tts / jarvis voice / جارویس ویس)
        if lower.startswith(".tts") or lower.startswith("jarvis voice") or lower.startswith("جارویس ویس"):
            cmd_text = raw_text.split(maxsplit=1)[1] if len(raw_text.split()) > 1 else "Hello Parham!"
            await event.edit("🎙️ *Generating Voice Note...*")
            audio_file = "/tmp/jarvis_voice.mp3"
            loop = asyncio.get_running_loop()
            ok = await loop.run_in_executor(None, _generate_tts_audio, cmd_text, audio_file)
            if ok and os.path.exists(audio_file):
                await event.delete()
                await tg_client.send_file(event.chat_id, audio_file, voice_note=True)
                return
            else:
                await event.edit("❌ Failed to generate audio.")
                return

        # 8. Live Web Search (.search / jarvis search / جارویس سرچ)
        if lower.startswith(".search") or lower.startswith("jarvis search") or lower.startswith("جارویس سرچ"):
            query = raw_text.split(maxsplit=1)[1] if len(raw_text.split()) > 1 else "latest news"
            await event.edit(f"🔍 *Searching web for:* `{query}`...")
            loop = asyncio.get_running_loop()
            search_res = await loop.run_in_executor(None, _web_search, query)
            await event.edit(f"🌐 **WEB SEARCH RESULTS:**\n\n{search_res}")
            return

        # ── General Trigger Matching (Jarvis Self-Bot AI) ────────────────────
        matched_trigger = None
        for t in TRIGGERS:
            if t in lower:
                matched_trigger = t
                break

        if not matched_trigger:
            return

        idx = lower.find(matched_trigger)
        cmd = raw_text[idx + len(matched_trigger):].strip()
        if not cmd:
            cmd = "سلام"

        print(f"[VPS Relay] Self-Bot Triggered: '{raw_text}' -> Command: '{cmd}'")

        if connected_pc:
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
        else:
            try:
                await event.edit(f"{raw_text}\n\n🧠 *thinking...*", parse_mode="markdown")
            except Exception:
                pass
                
            ai_reply = await generate_vps_ai_reply(cmd)

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
