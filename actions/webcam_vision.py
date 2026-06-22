import io
import base64
import json
import requests
from pathlib import Path

CONFIG_PATH = Path("config/api_keys.json")

def get_openrouter_key():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("openrouter_api_key", "")
    except Exception:
        return ""

def analyze_webcam(parameters: dict, player=None) -> str:
    """
    Captures a frame from the default webcam and sends it to OpenRouter's Qwen VL model for analysis.
    """
    api_key = get_openrouter_key()
    if not api_key:
        return "Error: OPENROUTER API KEY is missing in config/api_keys.json."

    prompt = parameters.get(
        "prompt",
        "Please describe in detail what you can see in this webcam image. "
        "Note any people, objects, text, or anything notable."
    )

    try:
        import cv2
    except ImportError:
        return "Error: opencv-python is not installed. Run: pip install opencv-python"

    try:
        # Open default webcam — use DirectShow on Windows to avoid MSMF errors
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)  # fallback
        if not cap.isOpened():
            return "Error: Could not access webcam. Make sure it is connected and not in use by another application."

        # Let the camera warm up for a moment
        import time
        time.sleep(0.5)

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return "Error: Failed to capture frame from webcam."

        # Resize to max 1024px on longest edge
        h, w = frame.shape[:2]
        max_dim = 1024
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        # Encode as JPEG -> Base64
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            return "Error: Failed to encode webcam frame."

        img_str = base64.b64encode(buffer.tobytes()).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/parhamje/JarvisAI",
            "X-Title": "JARVIS AI Node",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "qwen/qwen2.5-vl-72b-instruct:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                    ]
                }
            ]
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Webcam analysis failed: {e}"
