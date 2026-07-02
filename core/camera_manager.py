import threading
import time
import cv2

class CameraManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CameraManager, cls).__new__(cls)
                cls._instance._init_camera()
            return cls._instance

    def _init_camera(self):
        self._cap = None
        self._latest_frame = None
        self._running = False
        self._thread = None
        self._frame_lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        # Try DirectShow first on Windows
        self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._cap = cv2.VideoCapture(0)
            
        if self._cap.isOpened():
            # Lower resolution for background processing efficiency
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()
        else:
            self._running = False

    def _update_loop(self):
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                with self._frame_lock:
                    self._latest_frame = frame.copy()
            time.sleep(0.05) # ~20 FPS limit

    def get_frame(self):
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
            return None

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._cap:
            self._cap.release()
            self._cap = None

# Global accessor
_manager = None

def get_camera_manager():
    global _manager
    if _manager is None:
        _manager = CameraManager()
    return _manager
