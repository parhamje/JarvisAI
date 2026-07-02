import threading
import time
import cv2
import numpy as np
from core.camera_manager import get_camera_manager

class MotionDetector:
    def __init__(self, on_motion_detected, cooldown_seconds=300):
        self.on_motion_detected = on_motion_detected
        self.cooldown_seconds = cooldown_seconds
        self._running = False
        self._thread = None
        self._last_motion_time = 0
        self._cam = get_camera_manager()

    def start(self):
        if self._running:
            return
        self._cam.start()
        self._running = True
        self._thread = threading.Thread(target=self._motion_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._cam.stop()

    def _motion_loop(self):
        prev_gray = None
        
        while self._running:
            frame = self._cam.get_frame()
            if frame is None:
                time.sleep(0.5)
                continue
                
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if prev_gray is None:
                prev_gray = gray
                time.sleep(0.5)
                continue
                
            frame_delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) > 5000: # Threshold for significant movement (like a person)
                    motion_detected = True
                    break
                    
            if motion_detected:
                now = time.time()
                if now - self._last_motion_time > self.cooldown_seconds:
                    self._last_motion_time = now
                    # Trigger the callback
                    if self.on_motion_detected:
                        self.on_motion_detected()
                        
            # Update background frame slowly to adapt to lighting changes
            cv2.accumulateWeighted(gray, prev_gray.astype("float"), 0.5)
            prev_gray = cv2.convertScaleAbs(prev_gray)
            
            time.sleep(0.2) # ~5 FPS is plenty for motion detection
