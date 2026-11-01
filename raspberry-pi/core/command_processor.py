# =============================================================================
#  core/command_processor.py — Translate API commands → hardware actions
#
#  Registered with CommandListener so each command type has a clear,
#  validated handler.  Validation errors raise ValueError so the listener
#  can NACK the command back to the API with a meaningful error message.
# =============================================================================

from typing import Any, Dict

from core.event_handler import EventHandler
from utils import get_logger
import config

log = get_logger(__name__)

class CommandProcessor:
    """Maps incoming API command payloads to hardware actions."""

    def __init__(self, event_handler: EventHandler) -> None:
        self._events = event_handler

    def handle_capture(self, payload: Dict[str, Any]) -> None:
        camera_id = payload.get("camera_id")
        if camera_id is None:
            raise ValueError("'camera_id' is required in capture command payload")

        camera_id = int(camera_id)
        if camera_id not in config.CAMERA_INDICES:
            raise ValueError(
                f"camera_id {camera_id} is not in configured indices {config.CAMERA_INDICES}"
            )

        log.info("[CMD] capture  camera_id=%d", camera_id)
        self._events.on_remote_capture(camera_id=camera_id)

    def register_all(self, listener) -> None:
        listener.register("capture", self.handle_capture)
        log.info("All command handlers registered")