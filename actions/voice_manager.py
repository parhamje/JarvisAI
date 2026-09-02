"""
actions/voice_manager.py - Neural Voice & Audio Persona Manager for Jarvis

Supports:
- Gemini Live bidirectional voice presets (Charon, Aoede, Fenrir, Puck, Kore)
- High-fidelity Neural Edge-TTS fallback (British Ryan, Persian Farid, Persian Dilara)
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

CONFIG_PATH = get_base_dir() / "config" / "api_keys.json"

VOICE_PRESETS = {
    "jarvis_british": {
        "gemini_voice": "Charon",
        "edge_voice": "en-GB-RyanNeural",
        "description": "J.A.R.V.I.S — Paul Bettany Deep British Tone (Default)"
    },
    "fem_friday": {
        "gemini_voice": "Aoede",
        "edge_voice": "en-GB-SoniaNeural",
        "description": "F.R.I.D.A.Y — Kerry Condon Female Assistant Tone"
    },
    "jarvis_american": {
        "gemini_voice": "Puck",
        "edge_voice": "en-US-GuyNeural",
        "description": "American Quick Assistant (Puck)"
    },
    "persian_male": {
        "gemini_voice": "Charon",
        "edge_voice": "fa-IR-FaridNeural",
        "description": "Persian Male Neural Voice (Farid)"
    },
    "persian_female": {
        "gemini_voice": "Aoede",
        "edge_voice": "fa-IR-DilaraNeural",
        "description": "Persian Female Neural Voice (Dilara)"
    }
}

def get_active_voice() -> str:
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("voice_preset", "jarvis_british")
    except Exception:
        pass
    return "jarvis_british"

def get_gemini_voice_name() -> str:
    preset_key = get_active_voice()
    preset = VOICE_PRESETS.get(preset_key, VOICE_PRESETS["jarvis_british"])
    return preset.get("gemini_voice", "Charon")

def set_active_voice(preset_key: str) -> bool:
    if preset_key not in VOICE_PRESETS:
        return False
    try:
        data = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["voice_preset"] = preset_key
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[VoiceManager] Failed to set voice: {e}")
        return False

async def synthesize_edge_tts(text: str, voice: str = None) -> bytes:
    """Synthesizes text using edge_tts and returns PCM or MP3 bytes."""
    try:
        import edge_tts
    except ImportError:
        return b""

    if not voice:
        preset_key = get_active_voice()
        preset = VOICE_PRESETS.get(preset_key, VOICE_PRESETS["jarvis_british"])
        voice = preset.get("edge_voice", "en-GB-RyanNeural")

    communicate = edge_tts.Communicate(text, voice)
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    return b"".join(audio_chunks)
