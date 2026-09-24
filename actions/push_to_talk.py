"""
actions/push_to_talk.py
Global Push-To-Talk (PTT) for Windows using Win32 GetAsyncKeyState.

Enables instant hardware-level mic gating via `Ctrl + Space` without
requiring heavy external dependencies.
"""

import sys
import time
import ctypes
import threading
from typing import Callable, List

# Win32 Virtual-Key Codes
VK_CONTROL = 0x11
VK_SPACE   = 0x20


class PushToTalk:
    def __init__(self, default_enabled: bool = False):
        self._enabled = default_enabled
        self._is_windows = (sys.platform == "win32")
        self._lock = threading.Lock()
        self._listeners: List[Callable[[bool], None]] = []
        self._last_pressed_state = False
        self._watcher_running = False
        self._watcher_thread: threading.Thread | None = None

        if self._is_windows:
            self._user32 = ctypes.windll.user32
        else:
            self._user32 = None

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @is_enabled.setter
    def is_enabled(self, val: bool):
        with self._lock:
            changed = (self._enabled != val)
            self._enabled = val
        if changed:
            print(f"[PushToTalk] Mode set to {'ENABLED (Ctrl+Space to talk)' if val else 'DISABLED (Open Mic)'}")
            if val and not self._watcher_running:
                self.start_watcher()

    def set_enabled(self, val: bool):
        self.is_enabled = val

    def is_pressed(self) -> bool:
        """Checks if both Ctrl and Space are physically held down right now."""
        if not self._is_windows or not self._user32:
            return True

        ctrl_state = self._user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
        space_state = self._user32.GetAsyncKeyState(VK_SPACE) & 0x8000
        return bool(ctrl_state and space_state)

    def should_record(self) -> bool:
        """
        Gate check for incoming microphone audio chunk.
        Returns True if audio should be processed, False if muted by PTT.
        """
        with self._lock:
            if not self._enabled:
                return True
        return self.is_pressed()

    def add_listener(self, cb: Callable[[bool], None]):
        """Register a callback for when PTT press state changes: cb(is_pressed)."""
        with self._lock:
            if cb not in self._listeners:
                self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[bool], None]):
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    def _notify_listeners(self, pressed: bool):
        for cb in list(self._listeners):
            try:
                cb(pressed)
            except Exception as e:
                print(f"[PushToTalk] Listener callback error: {e}")

    def start_watcher(self):
        """Starts a background thread to detect key press/release state transitions for UI."""
        if self._watcher_running or not self._is_windows:
            return
        self._watcher_running = True

        def _loop():
            while self._watcher_running:
                if self.is_enabled:
                    pressed = self.is_pressed()
                    if pressed != self._last_pressed_state:
                        self._last_pressed_state = pressed
                        self._notify_listeners(pressed)
                time.sleep(0.03)  # ~30Hz polling for UI animation responsiveness

        self._watcher_thread = threading.Thread(target=_loop, name="PTT_Watcher", daemon=True)
        self._watcher_thread.start()

    def stop_watcher(self):
        self._watcher_running = False


# Singleton instance
ptt = PushToTalk(default_enabled=False)
