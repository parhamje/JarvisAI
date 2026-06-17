"""
wake_word.py — "Hey Jarvis" Wake Word Listener
Uses OpenWakeWord (offline, free) to detect the wake phrase.
Runs in a background daemon thread, separate audio stream from Gemini.
When detected: unmutes the mic so Jarvis starts listening.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False

try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False

try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    _OWW = True
except ImportError:
    _OWW = False


# ── Constants ─────────────────────────────────────────────────────────────────

_SAMPLE_RATE    = 16_000      # OpenWakeWord requires 16kHz
_CHUNK_FRAMES   = 1_280       # ~80ms per chunk (OWW requirement)
_SCORE_THRESH   = 0.5         # confidence threshold for "Hey Jarvis"
_COOLDOWN_SEC   = 3.0         # seconds to ignore after a detection (prevent double-fire)
_BEEP_FREQ      = 880         # Hz — wake tone
_BEEP_DUR       = 0.12        # seconds

# Built-in OWW model that most closely matches "Hey Jarvis"
# We use "hey_jarvis" if available, otherwise fall back to "alexa" as a placeholder
_PREFERRED_MODELS = ["hey_jarvis", "alexa"]


# ── Wake sound ────────────────────────────────────────────────────────────────

def _play_beep(freq: float = _BEEP_FREQ, duration: float = _BEEP_DUR,
               sample_rate: int = 44_100, volume: float = 0.4) -> None:
    """Play a short sine-wave beep to confirm wake detection."""
    if not _NUMPY or not _SD:
        return
    try:
        t    = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = (np.sin(2 * np.pi * freq * t) * volume * 32767).astype(np.int16)
        sd.play(wave, samplerate=sample_rate, blocking=False)
    except Exception as e:
        print(f"[WakeWord] Beep error: {e}")


# ── Main class ────────────────────────────────────────────────────────────────

class WakeWordListener:
    """
    Background listener for "Hey Jarvis".
    Usage:
        listener = WakeWordListener(on_wake=my_callback)
        listener.start()
        # ... later ...
        listener.stop()
    """

    def __init__(self, on_wake: Optional[Callable] = None):
        self._on_wake        = on_wake
        self._thread: Optional[threading.Thread] = None
        self._stop_event     = threading.Event()
        self._last_detection = 0.0
        self._model: Optional[OWWModel] = None
        self._active         = False

    def is_available(self) -> bool:
        return _OWW and _SD and _NUMPY

    def start(self) -> bool:
        if not self.is_available():
            missing = []
            if not _OWW:   missing.append("openwakeword")
            if not _SD:    missing.append("sounddevice")
            if not _NUMPY: missing.append("numpy")
            print(f"[WakeWord] Cannot start — missing: {', '.join(missing)}")
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="WakeWordListener",
        )
        self._thread.start()
        print("[WakeWord] Listener started — say 'Hey Jarvis' to activate")
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        print("[WakeWord] Listener stopped")

    def _load_model(self) -> bool:
        try:
            print("[WakeWord] Loading model...")
            # Try to load a "hey_jarvis" model if the user has downloaded one,
            # otherwise use the built-in wakeword models (alexa as default)
            base = Path(__file__).resolve().parent.parent / "models"
            custom = base / "hey_jarvis.onnx"

            if custom.exists():
                self._model = OWWModel(
                    wakeword_models=[str(custom)],
                    inference_framework="onnx",
                )
                print(f"[WakeWord] Custom model loaded: {custom}")
            else:
                # Use built-in openWakeWord models
                openwakeword.utils.download_models()
                self._model = OWWModel(inference_framework="onnx")
                print("[WakeWord] Built-in models loaded")
            return True
        except Exception as e:
            print(f"[WakeWord] Model load error: {e}")
            return False

    def _run(self) -> None:
        if not self._load_model():
            return

        self._active = True
        print("[WakeWord] Listening...")

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=_CHUNK_FRAMES,
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set():
                    time.sleep(0.05)
        except Exception as e:
            print(f"[WakeWord] Audio stream error: {e}")
        finally:
            self._active = False

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if self._model is None or self._stop_event.is_set():
            return
        try:
            audio = indata[:, 0].astype(np.int16)
            self._model.predict(audio)

            for model_name, scores in self._model.prediction_buffer.items():
                score = float(scores[-1]) if scores else 0.0
                if score >= _SCORE_THRESH:
                    now = time.time()
                    if now - self._last_detection > _COOLDOWN_SEC:
                        self._last_detection = now
                        self._on_detected(model_name, score)
        except Exception as e:
            print(f"[WakeWord] Predict error: {e}")

    def _on_detected(self, model_name: str, score: float) -> None:
        print(f"[WakeWord] Wake word detected! model={model_name} score={score:.3f}")
        _play_beep()
        if self._on_wake:
            try:
                self._on_wake()
            except Exception as e:
                print(f"[WakeWord] on_wake callback error: {e}")


# ── Singleton convenience ─────────────────────────────────────────────────────

_listener: Optional[WakeWordListener] = None


def get_listener() -> WakeWordListener:
    global _listener
    if _listener is None:
        _listener = WakeWordListener()
    return _listener


def start_wake_word(on_wake: Optional[Callable] = None) -> bool:
    """Start the global wake word listener with an optional callback."""
    global _listener
    _listener = WakeWordListener(on_wake=on_wake)
    return _listener.start()


def stop_wake_word() -> None:
    global _listener
    if _listener:
        _listener.stop()
