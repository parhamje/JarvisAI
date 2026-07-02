"""
media_control.py — Jarvis Media Controller
Simulates OS-level media keys to control music and video playback (Spotify, Apple Music, VLC, Browser).
"""
import time

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

def media_control(parameters: dict, player=None, speak=None) -> str:
    """
    Main entry point for media control.
    Supported actions:
        - play_pause
        - next_track
        - prev_track
        - volume_up
        - volume_down
        - volume_mute
    """
    if not _HAS_PYAUTOGUI:
        return "Failed to control media: pyautogui is not installed. Please run 'pip install pyautogui'."

    action = parameters.get("action", "").lower().strip()

    if action in ["play", "pause", "play_pause", "toggle"]:
        pyautogui.press("playpause")
        return "Toggled media playback."
    elif action in ["next", "skip", "next_track"]:
        pyautogui.press("nexttrack")
        return "Skipped to the next track."
    elif action in ["prev", "previous", "back", "prev_track"]:
        pyautogui.press("prevtrack")
        return "Went back to the previous track."
    elif action in ["vol_up", "volume_up", "louder"]:
        # Press a few times for a noticeable difference
        for _ in range(5):
            pyautogui.press("volumeup")
            time.sleep(0.01)
        return "Increased volume."
    elif action in ["vol_down", "volume_down", "quieter", "softer"]:
        for _ in range(5):
            pyautogui.press("volumedown")
            time.sleep(0.01)
        return "Decreased volume."
    elif action in ["mute", "unmute", "volume_mute"]:
        pyautogui.press("volumemute")
        return "Toggled volume mute."
    else:
        return f"Unknown media action: '{action}'. Supported actions: play_pause, next_track, prev_track, volume_up, volume_down, volume_mute."
