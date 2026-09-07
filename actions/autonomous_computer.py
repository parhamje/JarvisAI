import json
import time
import re
import sys
from pathlib import Path
from PIL import ImageGrab

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError:
    _HAS_PYAUTOGUI = False

try:
    import pyperclip
    _HAS_PYPERCLIP = True
except ImportError:
    _HAS_PYPERCLIP = False

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

API_CONFIG_PATH = get_base_dir() / "config" / "api_keys.json"

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()

def run_agent(task_description: str, player=None, speak=None):
    if not _HAS_PYAUTOGUI:
        msg = "PyAutoGUI is not installed. Please run: pip install pyautogui"
        if speak: speak(msg)
        return msg

    import google.generativeai as genai
    genai.configure(api_key=_get_api_key())
    model = genai.GenerativeModel("gemini-2.5-flash")

    screen_width, screen_height = pyautogui.size()
    max_steps = 18
    history = []

    if sys.platform == "win32":
        try:
            import ctypes
            hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                ctypes.windll.user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

    msg = f"Starting autonomous desktop execution for: {task_description}"
    print(f"[AutoAgent] {msg}")

    # 1. Non-Intrusive HUD Integration: Minimize full HUD to Mini-Orb so screen is unobstructed
    if player is not None:
        try:
            win = getattr(player, "_win", player)
            if hasattr(win, "_minimize_to_orb") and hasattr(win, "isVisible") and win.isVisible():
                print("[AutoAgent] 🪟 Minimizing HUD to Arc-Reactor Mini Widget during task execution...")
                win._minimize_to_orb()
            if hasattr(win, "_apply_state"):
                win._apply_state("THINKING")
        except Exception as e:
            print(f"[AutoAgent] HUD minimize note: {e}")

    if speak:
        speak("Taking control of the system to complete your request, Sir. Please keep your hands off the mouse.")

    time.sleep(0.8)

    for step in range(max_steps):
        print(f"\n[AutoAgent] ── Step {step+1}/{max_steps} ──")
        
        # 1. Capture high-fidelity screenshot
        try:
            screenshot = ImageGrab.grab()
        except Exception as e:
            err = f"Screenshot capture error: {e}"
            print(f"[AutoAgent] {err}")
            if speak: speak("Error capturing screen, Sir.")
            return err

        # 2. Build multi-modal spatial prompt
        prompt = f"""You are JARVIS's Autonomous Computer Control & Vision Agent.
Your ultimate goal is: {task_description}

Resolution: {screen_width}x{screen_height} (Screenshot dimensions: {screenshot.width}x{screenshot.height}).
Step: {step+1} of {max_steps}.

Action History:
{json.dumps(history[-5:], indent=2) if history else "None yet"}

Inspect the screenshot with extreme visual precision.
Decide the single best NEXT ACTION to progress towards achieving the goal.

Output ONLY a raw JSON object matching one of the following schemas:

1. CLICK (Left Click):
   {{
      "action": "CLICK",
      "box_2d": [ymin, xmin, ymax, xmax],
      "reason": "Description of element to click"
   }}

2. DOUBLE_CLICK (To open files, apps, desktop shortcuts):
   {{
      "action": "DOUBLE_CLICK",
      "box_2d": [ymin, xmin, ymax, xmax],
      "reason": "Description of element to double click"
   }}

3. RIGHT_CLICK (Context menu):
   {{
      "action": "RIGHT_CLICK",
      "box_2d": [ymin, xmin, ymax, xmax],
      "reason": "Why right clicking"
   }}

4. DRAG (Drag from source to destination):
   {{
      "action": "DRAG",
      "start_box": [ymin, xmin, ymax, xmax],
      "end_box": [ymin, xmin, ymax, xmax],
      "reason": "Why dragging"
   }}

5. TYPE (Type text - supports Persian, English, symbols, URLs):
   {{
      "action": "TYPE",
      "text": "Text to enter",
      "press_enter": true,
      "reason": "Why typing this text"
   }}

6. KEY_PRESS (Single key like enter, esc, tab, backspace, space, up, down):
   {{
      "action": "KEY_PRESS",
      "key": "enter",
      "reason": "Why pressing key"
   }}

7. HOTKEY (Shortcut combination):
   {{
      "action": "HOTKEY",
      "keys": ["win", "r"],
      "reason": "Why pressing hotkey"
   }}

8. SCROLL (Scroll up or down):
   {{
      "action": "SCROLL",
      "direction": "down",
      "amount": 300,
      "reason": "Why scrolling"
   }}

9. WAIT (Pause for application or webpage to load):
   {{
      "action": "WAIT",
      "seconds": 2,
      "reason": "Waiting for app/page to load"
   }}

10. LAUNCH_APP (Launch or start an application if it is not open or visible on screen):
   {{
      "action": "LAUNCH_APP",
      "app_name": "notepad",
      "reason": "Opening application to proceed with task"
   }}

11. DONE (Task is completed):
   {{
      "action": "DONE",
      "reason": "Brief summary of how the task was successfully completed"
   }}

IMPORTANT RULES & STRATEGIES:
- If the required app is not open or visible: You can use LAUNCH_APP with the app name (e.g. "notepad", "calc", "spotify", "chrome"), or use HOTKEY ["win", "r"] and TYPE the app name, or click on taskbar / desktop icon.
- For typing text, make sure the target input field or document area has been clicked and focused first.
- All bounding boxes `box_2d`, `start_box`, `end_box` MUST be in normalized [ymin, xmin, ymax, xmax] on a 1000x1000 scale.
- Output ONLY valid JSON. No markdown code blocks, no trailing comments.
"""

        try:
            response = model.generate_content([prompt, screenshot])
            response_text = _strip_fences(response.text)
            # Find json block if wrapped
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            action_data = json.loads(response_text)
        except Exception as e:
            err = f"Failed to get or parse action response: {e}"
            print(f"[AutoAgent] {err}")
            time.sleep(1)
            continue

        action_type = action_data.get("action", "").upper()
        reason = action_data.get("reason", "")
        print(f"[AutoAgent] ▶ Action: {action_type} | Reason: {reason}")
        history.append({"step": step+1, "action": action_type, "reason": reason})

        def box_to_coords(box):
            ymin, xmin, ymax, xmax = box
            center_x_norm = (xmin + xmax) / 2 / 1000.0
            center_y_norm = (ymin + ymax) / 2 / 1000.0
            tx = int(center_x_norm * screen_width)
            ty = int(center_y_norm * screen_height)
            return max(0, min(screen_width - 1, tx)), max(0, min(screen_height - 1, ty))

        try:
            if action_type == "CLICK":
                box = action_data.get("box_2d")
                if box and len(box) == 4:
                    tx, ty = box_to_coords(box)
                    print(f"[AutoAgent] 🖱 Clicking at ({tx}, {ty})")
                    pyautogui.moveTo(tx, ty, duration=0.4)
                    pyautogui.click()
                    time.sleep(0.8)

            elif action_type == "DOUBLE_CLICK":
                box = action_data.get("box_2d")
                if box and len(box) == 4:
                    tx, ty = box_to_coords(box)
                    print(f"[AutoAgent] 🖱 Double clicking at ({tx}, {ty})")
                    pyautogui.moveTo(tx, ty, duration=0.4)
                    pyautogui.doubleClick()
                    time.sleep(1.0)

            elif action_type == "RIGHT_CLICK":
                box = action_data.get("box_2d")
                if box and len(box) == 4:
                    tx, ty = box_to_coords(box)
                    print(f"[AutoAgent] 🖱 Right clicking at ({tx}, {ty})")
                    pyautogui.moveTo(tx, ty, duration=0.4)
                    pyautogui.rightClick()
                    time.sleep(0.8)

            elif action_type == "DRAG":
                sbox = action_data.get("start_box")
                ebox = action_data.get("end_box")
                if sbox and ebox:
                    sx, sy = box_to_coords(sbox)
                    ex, ey = box_to_coords(ebox)
                    print(f"[AutoAgent] 🖱 Dragging from ({sx}, {sy}) to ({ex}, {ey})")
                    pyautogui.moveTo(sx, sy, duration=0.3)
                    pyautogui.dragTo(ex, ey, duration=0.8, button='left')
                    time.sleep(0.8)

            elif action_type == "TYPE":
                text = action_data.get("text", "")
                press_enter = action_data.get("press_enter", False)
                print(f"[AutoAgent] ⌨ Typing: {text[:60]!r}")
                # Use clipboard paste to flawlessly support Persian, unicode, and paths
                if _HAS_PYPERCLIP:
                    try:
                        pyperclip.copy(text)
                        pyautogui.hotkey("ctrl", "v")
                    except Exception:
                        pyautogui.write(text, interval=0.02)
                else:
                    pyautogui.write(text, interval=0.02)

                if press_enter:
                    time.sleep(0.2)
                    pyautogui.press("enter")
                time.sleep(0.8)

            elif action_type == "KEY_PRESS":
                key = action_data.get("key", "").lower().strip()
                if key:
                    print(f"[AutoAgent] ⌨ Pressing key: {key}")
                    pyautogui.press(key)
                    time.sleep(0.5)

            elif action_type == "HOTKEY":
                keys = [k.lower().strip() for k in action_data.get("keys", [])]
                if keys:
                    print(f"[AutoAgent] ⌨ Pressing hotkey: {'+'.join(keys)}")
                    pyautogui.hotkey(*keys)
                    time.sleep(0.8)

            elif action_type == "SCROLL":
                direction = action_data.get("direction", "down").lower()
                amount = int(action_data.get("amount", 300))
                clicks = -amount if direction == "down" else amount
                print(f"[AutoAgent] 📜 Scrolling {direction} ({clicks})")
                pyautogui.scroll(clicks)
                time.sleep(0.6)

            elif action_type == "WAIT":
                sec = min(8, max(1, int(action_data.get("seconds", 2))))
                print(f"[AutoAgent] ⏳ Waiting {sec}s...")
                time.sleep(sec)

            elif action_type == "LAUNCH_APP":
                app_name = action_data.get("app_name", "").strip()
                print(f"[AutoAgent] 🚀 Launching application: {app_name}")
                if app_name:
                    import subprocess
                    try:
                        subprocess.Popen(f"start {app_name}", shell=True)
                    except Exception as e:
                        print(f"[AutoAgent] Error launching {app_name}: {e}")
                time.sleep(1.5)

            elif action_type == "DONE":
                msg = f"Task completed successfully: {reason}"
                print(f"[AutoAgent] ✅ {msg}")
                if player is not None:
                    try:
                        win = getattr(player, "_win", player)
                        if hasattr(win, "_apply_state"):
                            win._apply_state("LISTENING")
                    except Exception:
                        pass
                if speak:
                    speak("Task completed, Sir.")
                return msg

            else:
                print(f"[AutoAgent] ⚠️ Unknown action: {action_type}")

        except pyautogui.FailSafeException:
            msg = "Failsafe triggered by user (mouse cursor in screen corner). Autonomous control aborted."
            print(f"[AutoAgent] 🛑 {msg}")
            if speak: speak("Failsafe triggered. Autonomous control aborted.")
            return msg
        except Exception as e:
            print(f"[AutoAgent] Execution error during action {action_type}: {e}")

    # Reached step limit
    msg = f"Reached maximum steps ({max_steps}) without full completion."
    print(f"[AutoAgent] ⚠️ {msg}")
    if player is not None:
        try:
            win = getattr(player, "_win", player)
            if hasattr(win, "_apply_state"):
                win._apply_state("LISTENING")
        except Exception:
            pass
    if speak:
        speak("I have reached the step limit for this task, Sir.")
    return msg

def autonomous_computer(parameters: dict, player=None, speak=None) -> str:
    task = parameters.get("task", "") or parameters.get("goal", "") or parameters.get("description", "")
    if not task:
        return "Please provide a task description."
    return run_agent(task, player=player, speak=speak)

