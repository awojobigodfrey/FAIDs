# =============================================================================
#  core/event_handler.py — Orchestrates the PIR → Camera → Upload pipeline
#
#  When a PIR sensor fires, the sensor_id is used to select which camera to
#  use (sensor 0 → camera 0, sensor 1 → camera 1).  This is configurable
#  via SENSOR_CAMERA_MAP below.
# =============================================================================


from typing import Dict

from sensors.camera import CameraManager
from api.uploader import EventUploader
from actuators.led import LEDController
from utils import get_logger

log = get_logger(__name__)

# Maps sensor_id → camera_id
SENSOR_CAMERA_MAP: Dict[int, int] = {
    0: 0,
    1: 2,  # Updated to point to /dev/video2!
}

class EventHandler:
    def __init__(
        self, 
        camera_manager: CameraManager, 
        uploader: EventUploader,
        led_controller: LEDController
    ) -> None:
        self._cameras  = camera_manager
        self._uploader = uploader
        self._led = led_controller

    def on_pir_motion(self, sensor_id: int) -> None:
        # 1. Trigger the LED blink immediately!
        self._led.trigger_blink()

        camera_id = SENSOR_CAMERA_MAP.get(sensor_id)
        if camera_id is None:
            log.warning("PIR sensor %d triggered but no camera mapping defined", sensor_id)
            return

        log.info("PIR sensor %d → triggering camera %d capture", sensor_id, camera_id)

        filepath, metadata = self._cameras.capture_image(
            camera_id=camera_id,
            reason="pir_trigger",
            sensor_id=sensor_id,
        )

        if filepath:
            self._uploader.enqueue(filepath, metadata)
        else:
            log.error("PIR sensor %d: capture on camera %d failed", sensor_id, camera_id)

    def on_remote_capture(self, camera_id: int, reason: str = "remote_command") -> None:
        log.info("Remote capture triggered: camera %d", camera_id)
        filepath, metadata = self._cameras.capture_image(
            camera_id=camera_id,
            reason=reason,
        )
        if filepath:
            self._uploader.enqueue(filepath, metadata)
        else:
            log.error("Remote capture failed for camera %d", camera_id)