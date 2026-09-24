"""
actions/acoustic_guard.py
Acoustic Echo Guard & Self-Speech Suppression for JARVIS.

Prevents acoustic feedback loops where JARVIS hears its own voice through
speakers and attempts to reply to or transcribe itself.
Inspired by Mark-LIV and WebRTC AEC gating principles.
"""

import time
import threading
import numpy as np


class AcousticGuard:
    def __init__(
        self,
        tail_duration: float = 0.40,      # Seconds of tail buffer after output ends
        barge_in_enabled: bool = True,    # Allow deliberate loud user interruptions
        barge_in_threshold: float = 1600.0, # RMS threshold required to interrupt while JARVIS speaks
        echo_suppression_floor: float = 300.0, # Normal silence / noise floor
    ):
        self.tail_duration = tail_duration
        self.barge_in_enabled = barge_in_enabled
        self.barge_in_threshold = barge_in_threshold
        self.echo_suppression_floor = echo_suppression_floor

        self.enabled = True
        self._lock = threading.Lock()
        self._is_playing = False
        self._last_playback_time = 0.0
        self._last_output_rms = 0.0
        self._suppressed_chunks_count = 0
        self._passed_chunks_count = 0

    def set_enabled(self, enabled: bool):
        with self._lock:
            self.enabled = enabled

    def is_enabled(self) -> bool:
        with self._lock:
            return self.enabled

    def on_playback_start(self):
        with self._lock:
            self._is_playing = True
            self._last_playback_time = time.time()

    def on_playback_chunk(self, chunk: bytes):
        """Called whenever a PCM chunk is sent to the speaker output."""
        now = time.time()
        with self._lock:
            self._is_playing = True
            self._last_playback_time = now
            # Sample RMS of speaker output to calibrate echo level
            try:
                samples = np.frombuffer(chunk, dtype=np.int16)
                if len(samples) > 0:
                    self._last_output_rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
            except Exception:
                pass

    def on_playback_stop(self):
        """Called when playback stream goes idle."""
        with self._lock:
            self._is_playing = False
            self._last_playback_time = time.time()

    def is_in_playback_or_tail(self) -> bool:
        """Returns True if speakers are actively playing or in tail latency decay window."""
        with self._lock:
            if not self.enabled:
                return False
            if self._is_playing:
                return True
            elapsed = time.time() - self._last_playback_time
            return elapsed < self.tail_duration

    def calculate_rms(self, pcm_bytes: bytes) -> float:
        """Vectorized RMS energy calculation."""
        if not pcm_bytes:
            return 0.0
        try:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            if len(samples) == 0:
                return 0.0
            return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        except Exception:
            return 0.0

    def should_suppress_input(self, input_pcm: bytes) -> bool:
        """
        Determines whether an incoming microphone audio chunk should be suppressed.
        Returns True if the chunk is self-echo, False if genuine user speech.
        """
        if not self.enabled:
            return False

        now = time.time()
        with self._lock:
            is_active = self._is_playing
            last_play = self._last_playback_time
            tail = self.tail_duration
            barge_in = self.barge_in_enabled
            barge_thresh = self.barge_in_threshold

        elapsed = now - last_play
        is_in_echo_window = is_active or (elapsed < tail)

        if not is_in_echo_window:
            with self._lock:
                self._passed_chunks_count += 1
            return False

        # If in echo window, check energy
        input_rms = self.calculate_rms(input_pcm)

        # In tail window (speakers just stopped within tail_duration):
        if not is_active and (elapsed < tail):
            # Acoustic reverberation decay window — suppress everything unless deliberate user shout
            if input_rms < barge_thresh:
                with self._lock:
                    self._suppressed_chunks_count += 1
                return True
            else:
                with self._lock:
                    self._passed_chunks_count += 1
                return False

        # In active playback:
        if is_active:
            if barge_in and input_rms >= barge_thresh:
                # User is speaking loudly over speaker output -> allow barge-in
                with self._lock:
                    self._passed_chunks_count += 1
                return False
            else:
                # Suppress speaker feedback
                with self._lock:
                    self._suppressed_chunks_count += 1
                return True

        return False

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "is_playing": self._is_playing,
                "suppressed_chunks": self._suppressed_chunks_count,
                "passed_chunks": self._passed_chunks_count,
                "last_output_rms": round(self._last_output_rms, 1),
            }


# Singleton instance for system-wide access
acoustic_guard = AcousticGuard()
