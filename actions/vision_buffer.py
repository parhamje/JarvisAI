"""
actions/vision_buffer.py
Rolling Screen Vision Buffer for Zero-Latency Visual Awareness.

Maintains a fresh, compressed, and encoded screen frame in a thread-safe
background buffer so visual queries ("What is on my screen?", "Look at this")
respond instantaneously without 2-3 second capture delays.
"""

import io
import time
import base64
import threading
from dataclasses import dataclass
from typing import Optional

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    from PIL import Image, ImageGrab
    _PIL = True
except ImportError:
    _PIL = False


@dataclass
class VisionFrame:
    image: Optional["Image.Image"]
    jpeg_bytes: bytes
    base64_str: str
    timestamp: float
    width: int
    height: int


class VisionBuffer:
    def __init__(
        self,
        interval: float = 2.5,
        max_dim: int = 1024,
        jpeg_quality: int = 75,
    ):
        self.interval = interval
        self.max_dim = max_dim
        self.jpeg_quality = jpeg_quality

        self._lock = threading.Lock()
        self._latest_frame: Optional[VisionFrame] = None
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = False

        self._thread = threading.Thread(target=self._capture_loop, name="VisionBufferWorker", daemon=True)
        self._thread.start()
        print("[VisionBuffer] Background rolling screen buffer started (2.5s interval).")

    def stop(self):
        with self._lock:
            self._running = False

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def _grab_raw(self) -> Optional["Image.Image"]:
        """Captures screen using MSS (fastest) or PIL ImageGrab."""
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x01FF)
                if hdesk:
                    ctypes.windll.user32.SetThreadDesktop(hdesk)
            except Exception:
                pass

        if _MSS:
            try:
                with mss.mss() as sct:
                    monitors = sct.monitors
                    # Use primary display or combined
                    target = monitors[1] if len(monitors) > 1 else monitors[0]
                    sct_img = sct.grab(target)
                    return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception:
                pass

        if _PIL:
            try:
                img = ImageGrab.grab()
                if img.mode != "RGB":
                    img = img.convert("RGB")
                return img
            except Exception:
                pass

        return None

    def _process_image(self, img: "Image.Image") -> VisionFrame:
        """Downscales, compresses, and base64 encodes the image."""
        w, h = img.size
        if w > self.max_dim or h > self.max_dim:
            img.thumbnail((self.max_dim, self.max_dim), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self.jpeg_quality, optimize=False)
        jpeg_bytes = buf.getvalue()
        b64_str = base64.b64encode(jpeg_bytes).decode("utf-8")

        return VisionFrame(
            image=img,
            jpeg_bytes=jpeg_bytes,
            base64_str=b64_str,
            timestamp=time.time(),
            width=img.width,
            height=img.height,
        )

    def _capture_loop(self):
        # Initial capture immediately
        try:
            raw = self._grab_raw()
            if raw:
                frame = self._process_image(raw)
                with self._lock:
                    self._latest_frame = frame
        except Exception as e:
            print(f"[VisionBuffer] Initial capture error: {e}")

        while self._running:
            time.sleep(self.interval)
            with self._lock:
                if not self._running or self._paused:
                    continue

            try:
                raw = self._grab_raw()
                if raw:
                    frame = self._process_image(raw)
                    with self._lock:
                        self._latest_frame = frame
            except Exception as e:
                # Silently catch transient capture glitches (e.g. desktop locked)
                pass

    def get_latest_frame(self, max_age: float = 4.0) -> Optional[VisionFrame]:
        """
        Retrieves the latest cached frame. If older than max_age or not yet captured,
        captures synchronously on demand.
        """
        now = time.time()
        with self._lock:
            if self._latest_frame and (now - self._latest_frame.timestamp <= max_age):
                return self._latest_frame

        # Fallback: capture on-demand
        return self.capture_fresh_frame()

    def capture_fresh_frame(self) -> Optional[VisionFrame]:
        """Forces an instant capture and updates the buffer."""
        try:
            raw = self._grab_raw()
            if not raw:
                return None
            frame = self._process_image(raw)
            with self._lock:
                self._latest_frame = frame
            return frame
        except Exception as e:
            print(f"[VisionBuffer] On-demand capture failed: {e}")
            return None

    def get_base64_jpeg(self) -> str:
        """Returns base64 string of the most recent frame."""
        frame = self.get_latest_frame()
        return frame.base64_str if frame else ""


# Singleton instance
vision_buffer = VisionBuffer()
