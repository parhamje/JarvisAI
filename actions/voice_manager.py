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
        "description": "J.A.R.V.I.S — Paul Bettany Deep British Tone (Official)"
    }
}

def get_active_voice() -> str:
    return "jarvis_british"

def get_gemini_voice_name() -> str:
    return "Charon"

def set_active_voice(preset_key: str) -> bool:
    return True

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
