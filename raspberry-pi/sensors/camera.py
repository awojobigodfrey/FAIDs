# =============================================================================
#  sensors/camera.py — USB camera handler (OpenCV)
#
#  CameraManager owns all camera captures and exposes a thread-safe
#  capture_image() method.  Cameras are opened lazily on first capture
#  and released automatically after an idle timeout to free USB bandwidth.
#
#  Fixes applied:
#   • All OpenCV operations wrapped in try/except — USB disconnects are
#     caught and logged; the calling thread always gets a clean return value
#   • Reaper loop uses a stop event instead of while True — no race against
#     release_all() during shutdown
# =============================================================================

import os
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

import cv2

import config
from utils import get_logger

log = get_logger(__name__)


class _CameraHandle:
    """Internal wrapper around a single cv2.VideoCapture."""

    def __init__(self, index: int) -> None:
        self.index = index
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_used: float = 0.0
        self.lock = threading.Lock()

    def open(self) -> bool:
        if self.cap and self.cap.isOpened():
            return True

        log.info("Opening camera %d (device /dev/video%d)", self.index, self.index)
        try:
            cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
            if not cap.isOpened():
                log.error("Camera %d: device did not open", self.index)
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            # Give the sensor time to auto-expose
            time.sleep(0.5)
            self.cap = cap
            return True

        except Exception as exc:
            log.error("Camera %d: exception during open: %s", self.index, exc)
            self.cap = None
            return False

    def grab_and_read(self) -> Tuple[bool, Optional[object]]:
        """
        Flush stale buffered frames then read a fresh one.
        Returns (success, frame).  Catches any OpenCV exception so the
        caller never sees a crash from a USB disconnect mid-capture.
        """
        try:
            # Discard buffered frames from the driver queue
            for _ in range(3):
                self.cap.grab()
            ret, frame = self.cap.read()
            return ret, frame if ret else None
        except Exception as exc:
            log.error("Camera %d: exception during capture: %s", self.index, exc)
            # Force a re-open on the next attempt
            self._force_release()
            return False, None

    def release(self) -> None:
        if self.cap:
            log.info("Releasing camera %d", self.index)
            self._force_release()

    def _force_release(self) -> None:
        """Release without guarding on self.cap being truthy."""
        try:
            if self.cap:
                self.cap.release()
        except Exception as exc:
            log.warning("Camera %d: exception during release: %s", self.index, exc)
        finally:
            self.cap = None

    @property
    def is_open(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


class CameraManager:
    """
    Thread-safe manager for multiple USB cameras.

    Usage
    -----
    manager = CameraManager()
    filepath, metadata = manager.capture_image(camera_id=0, reason="pir_trigger")
    """

    def __init__(self) -> None:
        self._handles: Dict[int, _CameraHandle] = {
            idx: _CameraHandle(idx) for idx in config.CAMERA_INDICES
        }
        self._stop_event = threading.Event()

        # Background thread to release idle cameras
        self._reaper = threading.Thread(
            target=self._reaper_loop,
            name="camera-reaper",
            daemon=True,
        )
        self._reaper.start()

        # Ensure the image save directory exists
        os.makedirs(config.IMAGE_SAVE_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_image(
        self,
        camera_id: int,
        reason: str = "manual",
        sensor_id: Optional[int] = None,
    ) -> Tuple[Optional[str], dict]:
        """
        Capture a single frame from *camera_id* and save it to disk.

        Returns
        -------
        filepath : str | None
            Absolute path to the saved JPEG, or None on failure.
        metadata : dict
            Event metadata to accompany the upload.
        """
        if camera_id not in self._handles:
            log.error("Camera ID %d is not configured", camera_id)
            return None, {}

        handle = self._handles[camera_id]

        with handle.lock:
            if not handle.open():
                return None, {}

            # Mark as active BEFORE the operation — this prevents the reaper
            # from treating a slow or hung capture as an idle camera and
            # racing to release it mid-operation.
            handle.last_used = time.time()
            ret, frame = handle.grab_and_read()
            handle.last_used = time.time()  # update again with actual finish time

        if not ret or frame is None:
            log.error("Camera %d: failed to capture frame", camera_id)
            return None, {}

        # ----------------------------------------------------------------
        # Save the frame
        # ----------------------------------------------------------------
        timestamp = datetime.utcnow()
        filename  = (
            f"cam{camera_id}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        )
        filepath = os.path.join(config.IMAGE_SAVE_DIR, filename)

        try:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY]
            success = cv2.imwrite(filepath, frame, encode_params)
        except Exception as exc:
            log.error("Camera %d: exception writing image: %s", camera_id, exc)
            return None, {}

        if not success:
            log.error("Camera %d: cv2.imwrite returned False for %s", camera_id, filepath)
            return None, {}

        log.info("Camera %d: captured → %s  (reason=%s)", camera_id, filepath, reason)

        metadata = {
            "node_id":    config.NODE_ID,
            "camera_id":  camera_id,
            "sensor_id":  sensor_id,
            "reason":     reason,
            "timestamp":  timestamp.isoformat() + "Z",
            "resolution": f"{config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}",
        }
        return filepath, metadata

    def release_all(self) -> None:
        """
        Stop the reaper first, then release every open camera.
        Stopping the reaper before touching handles prevents any race
        between the reaper waking up and this method releasing handles.
        """
        self._stop_event.set()
        for handle in self._handles.values():
            with handle.lock:
                handle.release()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reaper_loop(self) -> None:
        """
        Periodically release cameras that have been idle too long.
        Uses stop_event.wait() instead of time.sleep() so it wakes
        immediately when release_all() signals shutdown.
        """
        while not self._stop_event.wait(timeout=10):
            now = time.time()
            for handle in self._handles.values():
                with handle.lock:
                    if handle.is_open:
                        idle = now - handle.last_used
                        if idle > config.CAMERA_RELEASE_TIMEOUT:
                            log.debug(
                                "Camera %d idle for %.0fs — releasing",
                                handle.index,
                                idle,
                            )
                            handle.release()
