import io
import base64
import json
import requests
from pathlib import Path
from PIL import ImageGrab

CONFIG_PATH = Path("config/api_keys.json")

def get_openrouter_key():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("openrouter_api_key", "")
    except Exception:
        return ""

def analyze_screen(parameters: dict, player=None) -> str:
    """
    Takes a screenshot, compresses it, and sends it to OpenRouter's Qwen VL model.
    """
    api_key = get_openrouter_key()
    if not api_key:
        return "Error: OPENROUTER API KEY is missing in config/api_keys.json. Please add it via Settings."
        
    prompt = parameters.get("prompt", "Please describe what is currently visible on my screen. Pay attention to any open applications, specific text, or error messages.")
    
    try:
        # Zero-latency frame from rolling buffer if available
        img_str = ""
        try:
            from actions.vision_buffer import vision_buffer
            frame = vision_buffer.get_latest_frame(max_age=3.5)
            if frame and frame.base64_str:
                img_str = frame.base64_str
        except Exception:
            pass

        if not img_str:
            # Fallback capture
            screenshot = ImageGrab.grab()
            max_dim = 1024
            if screenshot.width > max_dim or screenshot.height > max_dim:
                screenshot.thumbnail((max_dim, max_dim))
            if screenshot.mode != 'RGB':
                screenshot = screenshot.convert('RGB')
            buffered = io.BytesIO()
            screenshot.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        
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
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_str}"
                            }
                        }
                    ]
                }
            ]
        }
        
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
        
    except Exception as e:
        return f"Failed to analyze screen: {e}"
