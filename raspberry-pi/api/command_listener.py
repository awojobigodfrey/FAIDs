# =============================================================================
#  api/command_listener.py — SSE-based command listener
#
#  Opens a persistent GET /events/stream connection using requests(stream=True)
#  and parses Server-Sent Events line by line.
#
#  SSE wire format (text/event-stream):
#      event: command
#      data: {"id":"...","type":"capture","payload":{"camera_id":0}}
#
#      event: heartbeat
#      data: {}
#
#  Reliability
#  ───────────
#  • If the connection drops (network blip, server restart, read timeout):
#    the listener reconnects automatically with exponential backoff
#    (starts at SSE_RECONNECT_BASE_DELAY, caps at SSE_RECONNECT_MAX_DELAY).
#  • Commands missed while offline are the API server's responsibility
#    to re-deliver (e.g. via a persistent session / Last-Event-ID header).
#    The listener sends the Last-Event-ID header on every reconnect so the
#    server can replay any missed events.
#  • Each successfully processed command is ACKed back to the API.
# =============================================================================

import json
import threading
import time
from typing import Callable, Dict, Any, Optional

import requests

import config
from utils import get_logger

log = get_logger(__name__)

_STREAM_URL = config.API_BASE_URL.rstrip("/") + config.ENDPOINT_SSE_STREAM
_ACK_URL    = config.API_BASE_URL.rstrip("/") + config.ENDPOINT_ACK_COMMAND

CommandHandler = Callable[[Dict[str, Any]], None]

_HEADERS = {
    "X-API-Key":  config.API_KEY,
    "X-Node-ID":  config.NODE_ID,
    "Accept":     "text/event-stream",
    "Cache-Control": "no-cache",
}


class CommandListener:
    """
    SSE client that listens for backend commands in a dedicated thread.

    Register handlers before calling start():
        listener.register("capture",   my_capture_fn)
        listener.register("siren",     my_siren_fn)
        listener.register("siren_off", my_siren_off_fn)
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, CommandHandler] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_event_id: Optional[str] = None  # for SSE resume

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, command_type: str, handler: CommandHandler) -> None:
        self._handlers[command_type] = handler
        log.debug("Registered SSE handler for command type '%s'", command_type)

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._listener_loop,
            name="sse-command-listener",
            daemon=True,
        )
        self._thread.start()
        log.info("CommandListener (SSE) started  →  %s", _STREAM_URL)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=config.SSE_READ_TIMEOUT + 2)
        log.info("CommandListener stopped")

    # ------------------------------------------------------------------
    # Listener loop — runs in its own thread
    # ------------------------------------------------------------------

    def _listener_loop(self) -> None:
        backoff = config.SSE_RECONNECT_BASE_DELAY

        while not self._stop_event.is_set():
            try:
                self._connect_and_read()
                # Only reaches here on a clean mid-stream disconnect (the
                # connection was established and then dropped normally).
                # Reset backoff — the server is reachable.
                backoff = config.SSE_RECONNECT_BASE_DELAY

            except requests.RequestException as exc:
                # Connection was never established (API down, DNS failure,
                # timeout before first byte, non-2xx status).
                # Do NOT reset backoff — let it grow so we don't hammer a
                # server that is clearly unavailable.
                log.warning("SSE connect failed: %s — retrying in %.0fs", exc, backoff)

            except Exception:  # noqa: BLE001
                # Unexpected non-network error — don't reset backoff either
                log.exception("Unexpected error in SSE listener loop")

            if self._stop_event.is_set():
                break

            log.info("SSE reconnecting in %.0fs …", backoff)
            self._stop_event.wait(timeout=backoff)
            backoff = min(
                backoff * config.SSE_RECONNECT_BACKOFF_FACTOR,
                config.SSE_RECONNECT_MAX_DELAY,
            )

    def _connect_and_read(self) -> None:
        """
        Open one SSE connection and read events until the connection closes
        or _stop_event is set.
        """
        headers = dict(_HEADERS)
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id

        log.info("Opening SSE stream connection …")

        # Let requests.RequestException propagate to _listener_loop so it
        # can apply the correct backoff (not reset it on a failed connect).
        resp = requests.get(
            _STREAM_URL,
            headers=headers,
            params={"node_id": config.NODE_ID},
            stream=True,
            timeout=(config.REQUEST_TIMEOUT[0], config.SSE_READ_TIMEOUT),
        )
        resp.raise_for_status()

        log.info("SSE stream connected (HTTP %d)", resp.status_code)

        # SSE parser state
        event_type = "message"
        data_lines = []
        event_id   = None

        try:
            for raw_line in resp.iter_lines(
                chunk_size=None, decode_unicode=True
            ):
                if self._stop_event.is_set():
                    break

                # ── Per-event try/except ───────────────────────────────
                # Catches parsing errors and bad dispatch payloads for a
                # single event (UnicodeDecodeError, KeyError, json errors,
                # unexpected exceptions from handlers, etc.).
                # The connection stays open — only the offending event is
                # skipped.  Network errors from iter_lines() still propagate
                # to the outer except so the connection is closed and
                # reconnected correctly.
                try:
                    # Empty line → dispatch accumulated event
                    if raw_line == "":
                        if data_lines:
                            self._dispatch(
                                event_type=event_type,
                                data="\n".join(data_lines),
                                event_id=event_id,
                            )
                        # Reset parser state for next event
                        event_type = "message"
                        data_lines = []
                        event_id   = None
                        continue

                    if raw_line.startswith(":"):
                        # SSE comment / keep-alive — ignore
                        continue

                    if ":" in raw_line:
                        field, _, value = raw_line.partition(":")
                        value = value.lstrip(" ")
                    else:
                        field = raw_line
                        value = ""

                    if field == "data":
                        data_lines.append(value)
                    elif field == "event":
                        event_type = value
                    elif field == "id":
                        event_id = value
                        self._last_event_id = value
                    elif field == "retry":
                        # Server suggests a reconnect interval (ms) — our
                        # config values take precedence.
                        pass

                except Exception as exc:  # noqa: BLE001
                    log.error(
                        "SSE: error processing event (skipping) — %s: %s",
                        type(exc).__name__, exc,
                    )
                    # Reset parser state so the next event starts clean
                    event_type = "message"
                    data_lines = []
                    event_id   = None

        except requests.RequestException as exc:
            # Network-level failure — close and reconnect
            log.warning("SSE stream error: %s", exc)
        finally:
            resp.close()

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, event_type: str, data: str, event_id: Optional[str]) -> None:
        # Ignore heartbeat / keep-alive events
        if event_type in ("heartbeat", "ping", "message") and data in ("{}", ""):
            log.debug("SSE heartbeat received")
            return

        if event_type != "command":
            log.debug("SSE: ignoring event type '%s'", event_type)
            return

        try:
            cmd = json.loads(data)
        except json.JSONDecodeError:
            log.error("SSE: could not parse command JSON: %r", data)
            return

        cmd_id   = cmd.get("id", event_id or "unknown")
        cmd_type = cmd.get("type", "")
        payload  = cmd.get("payload", {})

        log.info(
            "SSE command received: id=%s  type=%s  payload=%s",
            cmd_id, cmd_type, payload,
        )

        handler = self._handlers.get(cmd_type)
        if handler is None:
            log.warning("No handler for command type '%s'", cmd_type)
            self._ack(cmd_id, success=False, error=f"Unknown type: {cmd_type}")
            return

        try:
            handler(payload)
            self._ack(cmd_id, success=True)
        except Exception as exc:  # noqa: BLE001
            log.exception("Handler for '%s' raised an exception", cmd_type)
            self._ack(cmd_id, success=False, error=str(exc))

    # ------------------------------------------------------------------
    # ACK
    # ------------------------------------------------------------------

    def _ack(self, cmd_id: str, success: bool, error: str = "") -> None:
        url  = _ACK_URL.format(id=cmd_id)
        body: dict = {"success": success}
        if error:
            body["error"] = error
        try:
            requests.post(
                url,
                json=body,
                headers={
                    "X-API-Key": config.API_KEY,
                    "X-Node-ID": config.NODE_ID,
                },
                timeout=config.REQUEST_TIMEOUT,
            )
            log.debug("ACK sent for command %s (success=%s)", cmd_id, success)
        except requests.RequestException as exc:
            log.warning("Failed to ACK command %s: %s", cmd_id, exc)
