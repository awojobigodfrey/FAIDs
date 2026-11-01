# =============================================================================
#  sensors/pir.py — PIR motion sensor handler (gpiozero implementation)
# =============================================================================

import time
from typing import Callable

from gpiozero import MotionSensor

import config
from utils import get_logger

log = get_logger(__name__)


class PIRSensor:
    """
    Represents a single PIR motion sensor connected to a GPIO pin using gpiozero.
    """

    def __init__(
        self,
        sensor_id: int,
        pin: int,
        on_motion: Callable[[int], None],
        cooldown: int = config.PIR_COOLDOWN_SECONDS,
    ) -> None:
        self.sensor_id = sensor_id
        self.pin = pin
        self._on_motion_callback = on_motion
        self._cooldown = cooldown

        self._last_trigger: float = 0.0
        self._active = False
        self._sensor = None
        
        log.info("PIR sensor %d initialized on GPIO %d (gpiozero)", self.sensor_id, self.pin)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialize the sensor and attach the motion callback."""
        if self._active:
            log.warning("PIR sensor %d is already running", self.sensor_id)
            return

        # Initialize the MotionSensor (pull_up=False matches the old PUD_DOWN behavior)
        self._sensor = MotionSensor(self.pin, pull_up=False)
        
        # Attach the callback natively via gpiozero
        self._sensor.when_motion = self._handle_motion
        
        self._active = True
        log.info("PIR sensor %d monitoring started", self.sensor_id)

    def stop(self) -> None:
        """Detach the callback and release the GPIO pin."""
        self._active = False
        if self._sensor:
            self._sensor.close()
            self._sensor = None
        log.info("PIR sensor %d monitoring stopped", self.sensor_id)

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_motion(self) -> None:
        """
        Invoked automatically by gpiozero when the pin goes HIGH.
        Applies the cooldown logic before dispatching the user callback.
        """
        if not self._active:
            return

        now = time.time()
        elapsed = now - self._last_trigger

        if elapsed < self._cooldown:
            log.debug(
                "PIR sensor %d: motion suppressed (cooldown %.1fs remaining)",
                self.sensor_id,
                self._cooldown - elapsed,
            )
            return

        self._last_trigger = now
        log.info(
            "PIR sensor %d: MOTION DETECTED on GPIO %d",
            self.sensor_id,
            self.pin,
        )
        
        try:
            self._on_motion_callback(self.sensor_id)
        except Exception:
            log.exception(
                "PIR sensor %d: error in on_motion callback", self.sensor_id
            )