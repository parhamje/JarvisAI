"""
browser_agent.py — Autonomous web browser control via Playwright.
JARVIS uses this to navigate real websites, click elements, fill forms,
extract content, and take screenshots with vision analysis.
"""
import asyncio
import base64
import json
import requests
from pathlib import Path

CONFIG_PATH = Path("config/api_keys.json")

def _get_openrouter_key() -> str:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("openrouter_api_key", "")
    except Exception:
        return ""


def _vision_analyze(img_bytes: bytes, prompt: str) -> str:
    """Send a screenshot to Qwen for visual analysis."""
    api_key = _get_openrouter_key()
    if not api_key:
        return "[No OpenRouter key - cannot analyze screenshot]"
    img_str = base64.b64encode(img_bytes).decode("utf-8")
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/parhamje/JarvisAI",
                "X-Title": "JARVIS AI Node",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen/qwen2.5-vl-72b-instruct:free",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
                ]}]
            },
            timeout=45
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Vision error: {e}]"


async def _run_browser(parameters: dict) -> str:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return "Error: playwright is not installed. Run: pip install playwright && python -m playwright install chromium"

    action   = parameters.get("action", "navigate").lower()
    url      = parameters.get("url", "")
    selector = parameters.get("selector", "")    # CSS selector or text
    text     = parameters.get("text", "")
    prompt   = parameters.get("prompt", "Describe what you see on this webpage in detail.")
    scroll_dir = parameters.get("direction", "down")
    wait_ms  = int(parameters.get("wait_ms", 1500))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False so user can see it
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            result = ""

            if action == "navigate":
                if not url:
                    return "Error: 'url' is required for the navigate action."
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(wait_ms)
                title = await page.title()
                result = f"Navigated to: {url}\nPage title: {title}"

            elif action == "click":
                if selector:
                    await page.click(selector, timeout=10000)
                else:
                    # Try to find by text
                    await page.get_by_text(text, exact=False).first.click(timeout=10000)
                await page.wait_for_timeout(wait_ms)
                result = f"Clicked: '{selector or text}'"

            elif action == "type":
                if selector:
                    await page.fill(selector, text)
                else:
                    await page.keyboard.type(text)
                result = f"Typed: '{text}'"

            elif action == "press":
                key = parameters.get("key", "Enter")
                await page.keyboard.press(key)
                await page.wait_for_timeout(wait_ms)
                result = f"Pressed key: {key}"

            elif action == "scroll":
                if scroll_dir == "down":
                    await page.mouse.wheel(0, 600)
                else:
                    await page.mouse.wheel(0, -600)
                await page.wait_for_timeout(500)
                result = f"Scrolled {scroll_dir}"

            elif action == "extract":
                # Get visible text content of the page
                content = await page.inner_text("body")
                # Truncate to avoid flooding context
                content = content.strip()
                if len(content) > 3000:
                    content = content[:3000] + "\n...[content truncated]"
                result = f"Page content:\n{content}"

            elif action == "screenshot":
                # Take a screenshot and analyze it with Qwen vision
                img_bytes = await page.screenshot(type="jpeg", quality=75)
                result = _vision_analyze(img_bytes, prompt)

            elif action == "search":
                # Navigate to google and search
                query = parameters.get("query", text)
                await page.goto(f"https://www.google.com/search?q={requests.utils.quote(query)}", timeout=30000)
                await page.wait_for_timeout(wait_ms)
                content = await page.inner_text("body")
                content = content.strip()
                if len(content) > 3000:
                    content = content[:3000] + "\n...[truncated]"
                result = f"Search results for '{query}':\n{content}"

            elif action == "wait":
                await page.wait_for_timeout(wait_ms)
                result = f"Waited {wait_ms}ms"

            else:
                result = f"Unknown browser action: {action}"

            return result

        finally:
            await browser.close()


def browser_agent(parameters: dict, player=None) -> str:
    """
    Synchronous wrapper around the async Playwright browser controller.
    """
    try:
        # Run in a new event loop to avoid conflicts with JARVIS's main asyncio loop
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run_browser(parameters))
        loop.close()
        return result
    except Exception as e:
        return f"Browser agent error: {e}"
