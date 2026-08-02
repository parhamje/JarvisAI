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
except ImportError:
    _HAS_PYAUTOGUI = False

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
        msg = "PyAutoGUI is not installed. Please run pip install pyautogui."
        if speak: speak(msg)
        return msg

    import google.generativeai as genai
    genai.configure(api_key=_get_api_key())
    # gemini-2.5-flash is excellent for spatial understanding
    model = genai.GenerativeModel("gemini-2.5-flash")

    screen_width, screen_height = pyautogui.size()
    max_steps = 15
    history = []

    msg = f"Starting autonomous control for task: {task_description}"
    print(f"[AutoAgent] {msg}")
    if speak: speak("Taking control of the mouse, Sir. Please do not move it.")

    for step in range(max_steps):
        print(f"[AutoAgent] Step {step+1}/{max_steps}")
        
        # 1. Take a screenshot
        screenshot = ImageGrab.grab()
        # Resize if it's too huge to save tokens, though Gemini handles large images well.
        # We will keep it full resolution for accuracy in bounding boxes.
        
        # 2. Build prompt
        prompt = f"""You are an autonomous computer control agent.
Your ultimate task is: {task_description}

You are provided with a screenshot of the user's current screen.
Resolution is {screen_width}x{screen_height}.

History of actions taken so far:
{json.dumps(history, indent=2)}

You must decide the NEXT ACTION to take to progress towards the task.
Output ONLY a JSON block containing your action. Do not wrap in markdown or add explanations outside the JSON.

Available actions:
1. CLICK: Click on a specific UI element.
   To click, you must find the element on the screen and provide a bounding box in normalized 1000x1000 coordinates [ymin, xmin, ymax, xmax].
   {{
      "action": "CLICK",
      "box_2d": [ymin, xmin, ymax, xmax],
      "reason": "Why you are clicking here"
   }}
2. TYPE: Type text using the keyboard (useful after clicking a text field).
   {{
      "action": "TYPE",
      "text": "The text to type",
      "press_enter": true,
      "reason": "Why you are typing this"
   }}
3. HOTKEY: Press a keyboard shortcut (e.g., "win", "enter", "ctrl", "c").
   {{
      "action": "HOTKEY",
      "keys": ["win", "d"],
      "reason": "Why you are pressing this hotkey"
   }}
4. DONE: The task is successfully completed.
   {{
      "action": "DONE",
      "reason": "Explain how the task was completed"
   }}

IMPORTANT RULES:
- When providing `box_2d`, provide [ymin, xmin, ymax, xmax] scaled to a 1000x1000 grid. E.g., if a button is exactly in the center, box_2d would be [490, 490, 510, 510].
- Only output JSON.
"""

        try:
            response = model.generate_content([prompt, screenshot])
            response_text = _strip_fences(response.text)
            action_data = json.loads(response_text)
        except Exception as e:
            err = f"Failed to get or parse response from Gemini: {e}"
            print(f"[AutoAgent] {err}")
            return err

        action_type = action_data.get("action")
        reason = action_data.get("reason", "")
        print(f"[AutoAgent] Action: {action_type} | Reason: {reason}")
        
        history.append(action_data)

        try:
            if action_type == "CLICK":
                box = action_data.get("box_2d")
                if not box or len(box) != 4:
                    print("[AutoAgent] Invalid box_2d")
                    continue
                
                ymin, xmin, ymax, xmax = box
                
                # Convert 1000x1000 grid to actual screen pixels
                center_y_norm = (ymin + ymax) / 2 / 1000
                center_x_norm = (xmin + xmax) / 2 / 1000
                
                target_x = int(center_x_norm * screen_width)
                target_y = int(center_y_norm * screen_height)
                
                print(f"[AutoAgent] Clicking at ({target_x}, {target_y})")
                pyautogui.moveTo(target_x, target_y, duration=0.5)
                pyautogui.click()
                time.sleep(1) # wait for UI to react
                
            elif action_type == "TYPE":
                text = action_data.get("text", "")
                press_enter = action_data.get("press_enter", False)
                print(f"[AutoAgent] Typing text...")
                pyautogui.write(text, interval=0.02)
                if press_enter:
                    pyautogui.press("enter")
                time.sleep(1)
                
            elif action_type == "HOTKEY":
                keys = action_data.get("keys", [])
                print(f"[AutoAgent] Pressing hotkeys: {keys}")
                pyautogui.hotkey(*keys)
                time.sleep(1)
                
            elif action_type == "DONE":
                msg = f"Task completed: {reason}"
                print(f"[AutoAgent] {msg}")
                if speak: speak("I have finished the task, Sir.")
                return msg
                
            else:
                print(f"[AutoAgent] Unknown action: {action_type}")
                
        except pyautogui.FailSafeException:
            msg = "Failsafe triggered (mouse moved to corner). Autonomous control aborted."
            print(f"[AutoAgent] {msg}")
            if speak: speak("Failsafe triggered. Aborting control.")
            return msg
            
    msg = "Reached maximum steps without completing the task."
    if speak: speak(msg)
    return msg

def autonomous_computer(parameters: dict, player=None, speak=None) -> str:
    task = parameters.get("task", "")
    if not task:
        return "Please provide a task description."
        
    return run_agent(task, player, speak)
