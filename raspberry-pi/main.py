#!/usr/bin/env python3
# =============================================================================
#  main.py — Agri-IDS hardware node entry point
#
#  Boot sequence
#  ─────────────
#  
#  1. Instantiate hardware modules (cameras, siren)
#  2. Instantiate DB queue store (recovers any interrupted jobs automatically)
#  3. Instantiate service modules (uploader, SSE command listener)
#  4. Wire together via EventHandler and CommandProcessor
#  5. Start PIR monitoring threads
#  6. Start SSE command listener thread
#  7. Block on a signal-aware idle loop
#  8. On SIGINT / SIGTERM: graceful shutdown
#
#  Run as
#  ──────
#      sudo python3 main.py
# =============================================================================

import os
import signal
import sys
import time


import config
from sensors   import PIRSensor, CameraManager
from actuators import LEDController
from db        import QueueStore
from api       import EventUploader, CommandListener
from core      import EventHandler, CommandProcessor
from utils     import get_logger

log = get_logger("agri_ids.main")


def _ensure_dirs() -> None:
    """Create required runtime directories if they don't exist."""
    for path in [
        config.IMAGE_SAVE_DIR,
        os.path.dirname(config.DB_PATH),
    ]:
        if path:
            os.makedirs(path, exist_ok=True)



def shutdown(
    pir_sensors: list,
    led: LEDController,
    cameras: CameraManager,
    uploader: EventUploader,
    cmd_listener: CommandListener,
) -> None:
    """Ordered graceful shutdown — safe for SIGINT and SIGTERM."""
    log.info("── Shutdown initiated ──────────────────────────────────────")

    # 1. Stop accepting new PIR events
    for sensor in pir_sensors:
        sensor.stop()

    # 2. Stop the SSE command stream
    cmd_listener.stop()

    # 3. Drain the upload queue — give it up to 20 s to finish in-flight jobs
    #    Any remaining pending jobs are already in SQLite and will resume on
    #    the next boot.
    uploader.shutdown(timeout=20.0)

    # 4. Safe actuator state
    led.cleanup()

    # 5. Release camera resources
    cameras.release_all()


    log.info("── Shutdown complete ───────────────────────────────────────")


def main() -> None:
    log.info("═══════════════════════════════════════════════════════════")
    log.info("  Agri-IDS  |  Node: %s", config.NODE_ID)
    log.info("  PIR pins : %s", config.PIR_PINS)
    log.info("  Cameras  : %s", config.CAMERA_INDICES)
    log.info("  Relay pin: GPIO %d", config.RELAY_PIN)
    log.info("  API URL  : %s", config.API_BASE_URL)
    log.info("  DB path  : %s", config.DB_PATH)
    log.info("═══════════════════════════════════════════════════════════")

    _ensure_dirs()

    # ── Hardware modules ────────────────────────────────────────────────
    cameras = CameraManager()
    led  = LEDController()

    # ── Persistent queue (recovers interrupted jobs on boot) ────────────
    queue_store = QueueStore()

    pending = queue_store.pending_count()
    if pending:
        log.info("Boot recovery: %d job(s) pending in queue — will resume upload", pending)

    # ── Service modules ─────────────────────────────────────────────────
    uploader     = EventUploader(queue_store=queue_store)
    cmd_listener = CommandListener()

    # ── Core wiring ─────────────────────────────────────────────────────
    event_handler = EventHandler(camera_manager=cameras, uploader=uploader, led_controller=led)
    cmd_processor = CommandProcessor(
        event_handler=event_handler
    )
    cmd_processor.register_all(cmd_listener)

    # ── PIR sensors ─────────────────────────────────────────────────────
    pir_sensors = []
    for sensor_id, pin in enumerate(config.PIR_PINS):
        sensor = PIRSensor(
            sensor_id=sensor_id,
            pin=pin,
            on_motion=event_handler.on_pir_motion,
        )
        pir_sensors.append(sensor)

    for sensor in pir_sensors:
        sensor.start()

    # ── SSE command listener ─────────────────────────────────────────────
    cmd_listener.start()

    log.info("System ONLINE — waiting for events …")

    # ── Signal handlers ──────────────────────────────────────────────────
    stop_flag = [False]

    def _handle_signal(signum, frame):  # noqa: ANN001
        log.info("Signal %d received — initiating shutdown …", signum)
        stop_flag[0] = True

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Idle loop ────────────────────────────────────────────────────────
    try:
        while not stop_flag[0]:
            time.sleep(0.5)
    finally:
        shutdown(
            pir_sensors=pir_sensors,
            led=led,
            cameras=cameras,
            uploader=uploader,
            cmd_listener=cmd_listener,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
