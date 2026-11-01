# =============================================================================
#  api/uploader.py — Persistent upload worker
#
#  Design
#  ──────
#  • Captures are written to the SQLite queue immediately (never lost)
#  • A single worker thread drains the queue continuously
#  • Before each upload attempt, reachability is checked via a lightweight
#    socket connect — if offline, the worker backs off exponentially and
#    retries without burning bandwidth
#  • On success  → row deleted immediately from the queue
#  • On failure  → attempt counter incremented; if under the retry limit
#                  the row goes back to pending; otherwise marked failed
#                  and purged after the retention window
#  • A periodic purge thread cleans up old failed rows
# =============================================================================

import json
import os
import socket
import threading
import time
import urllib.parse

import requests

import config
from db import QueueStore
from utils import get_logger

log = get_logger(__name__)

_UPLOAD_URL = config.API_BASE_URL.rstrip("/") + config.ENDPOINT_EVENT_UPLOAD

_SESSION = requests.Session()
_SESSION.headers.update({
    "X-API-Key": config.API_KEY,
    "X-Node-ID": config.NODE_ID,
})


def _api_host() -> tuple:
    """Parse the API base URL into (hostname, port) for reachability checks."""
    parsed = urllib.parse.urlparse(config.API_BASE_URL)
    host   = parsed.hostname or "8.8.8.8"
    port   = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def _is_reachable() -> bool:
    """
    Lightweight connectivity check — attempts a TCP connect to the API host.
    Returns True if the socket handshake succeeds within 3 seconds.
    """
    host, port = _api_host()
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


class EventUploader:
    """
    Persistent, connectivity-aware upload worker.

    enqueue() is the only method callers need — it writes the job to SQLite
    and returns immediately.  The background worker thread handles the rest.
    """

    def __init__(self, queue_store: QueueStore) -> None:
        self._store = queue_store
        self._stop_event = threading.Event()

        # Worker thread — drains the queue
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="upload-worker",
            daemon=True,
        )

        # Purge thread — removes stale failed rows periodically
        self._purger = threading.Thread(
            target=self._purge_loop,
            name="upload-purger",
            daemon=True,
        )

        self._worker.start()
        self._purger.start()
        log.info("EventUploader started  →  %s", _UPLOAD_URL)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, filepath: str, metadata: dict) -> None:
        """
        Persist an upload job to SQLite and return immediately.
        The worker thread will pick it up asynchronously.
        """
        metadata_json = json.dumps(metadata)
        job_id = self._store.enqueue(filepath, metadata_json)
        log.info(
            "Upload job #%d queued: %s", job_id, os.path.basename(filepath)
        )

    def shutdown(self, timeout: float = 20.0) -> None:
        """Signal the worker to stop and wait for it to finish."""
        log.info("EventUploader: shutting down …")
        self._stop_event.set()
        self._worker.join(timeout=timeout)
        self._purger.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        backoff = config.UPLOAD_BACKOFF_BASE

        while not self._stop_event.is_set():
            job = self._store.claim_next()

            if job is None:
                # Queue is empty — idle wait before checking again
                self._stop_event.wait(timeout=2.0)
                continue

            # ── Connectivity check ─────────────────────────────────────
            if not _is_reachable():
                log.warning(
                    "Network unreachable — backing off %.0fs before retrying job #%d",
                    backoff, job["id"],
                )
                # Release the claim back to pending WITHOUT counting an attempt
                # — the job is not at fault, the network is
                self._store.release_to_pending(job["id"])
                self._stop_event.wait(timeout=backoff)
                backoff = min(
                    backoff * config.UPLOAD_BACKOFF_FACTOR,
                    config.UPLOAD_BACKOFF_MAX,
                )
                continue

            # Network is up — reset backoff
            backoff = config.UPLOAD_BACKOFF_BASE

            # ── Upload attempt ─────────────────────────────────────────
            success = self._attempt_upload(job)

            if success:
                self._store.mark_done(job["id"])
                if not config.KEEP_LOCAL_COPY:
                    self._delete_file(job["filepath"])
            else:
                will_retry = self._store.mark_failed_attempt(job["id"])
                if will_retry:
                    self._stop_event.wait(timeout=config.UPLOAD_BACKOFF_BASE)
                else:
                    # Job permanently failed — delete the image file so it
                    # doesn't accumulate on disk indefinitely
                    if not config.KEEP_LOCAL_COPY:
                        self._delete_file(job["filepath"])
                    log.error(
                        "Job #%d permanently abandoned after %d attempts — file removed",
                        job["id"], config.UPLOAD_MAX_RETRIES,
                    )

    def _attempt_upload(self, job: dict) -> bool:
        """
        POST the image and metadata to the API.
        Returns True on HTTP 2xx, False on any error.
        """
        filepath      = job["filepath"]
        metadata_json = job["metadata_json"]
        job_id        = job["id"]

        if not os.path.exists(filepath):
            log.error(
                "Job #%d: file no longer exists (%s) — dropping", job_id, filepath
            )
            # Treat as done so we don't loop forever on a missing file
            self._store.mark_done(job_id)
            return True

        try:
            with open(filepath, "rb") as fh:
                files = {"file": (os.path.basename(filepath), fh, "image/jpeg")}
                data  = {"metadata": metadata_json}
                resp  = _SESSION.post(
                    _UPLOAD_URL,
                    files=files,
                    data=data,
                    timeout=config.REQUEST_TIMEOUT,
                )
            resp.raise_for_status()
            event_id = resp.json().get("event_id", "?")
            log.info(
                "Job #%d uploaded (event_id=%s, HTTP %d)",
                job_id, event_id, resp.status_code,
            )
            return True

        except requests.RequestException as exc:
            log.warning("Job #%d upload failed: %s", job_id, exc)
            return False
        except OSError as exc:
            log.error("Job #%d file read error: %s", job_id, exc)
            return False

    # ------------------------------------------------------------------
    # Purge loop
    # ------------------------------------------------------------------

    def _purge_loop(self) -> None:
        """Periodically clean up stale failed rows from the queue DB."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=600)  # every 10 minutes
            if not self._stop_event.is_set():
                self._store.purge_failed()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _delete_file(filepath: str) -> None:
        try:
            os.remove(filepath)
            log.debug("Deleted local file: %s", filepath)
        except OSError as exc:
            log.warning("Could not delete %s: %s", filepath, exc)
