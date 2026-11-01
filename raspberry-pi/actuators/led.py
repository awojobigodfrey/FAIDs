import threading
from gpiozero import LED

import config
from utils import get_logger

log = get_logger(__name__)

class LEDController:
    """Controls the status LED using gpiozero."""

    def __init__(self) -> None:
        self._led = LED(config.LED_PIN)
        self._led.on()  # On constantly by default
        self._lock = threading.Lock()
        self._timer = None
        log.info("LED initialized on GPIO %d (Constantly ON)", config.LED_PIN)

    def trigger_blink(self) -> None:
        """Blink the LED rapidly for the configured duration, then return to solid ON."""
        with self._lock:
            # Cancel any existing timer if motion is detected back-to-back
            if self._timer:
                self._timer.cancel()
            
            # Start blinking in the background (0.2s on, 0.2s off)
            self._led.blink(on_time=0.2, off_time=0.2)
            log.info("LED blinking for %ds", config.LED_BLINK_DURATION)

            # Set a timer to return the LED to solid ON after 3 seconds
            self._timer = threading.Timer(config.LED_BLINK_DURATION, self._restore_solid)
            self._timer.daemon = True
            self._timer.start()

    def _restore_solid(self) -> None:
        with self._lock:
            self._led.on()
            self._timer = None

    def cleanup(self) -> None:
        self._led.close()