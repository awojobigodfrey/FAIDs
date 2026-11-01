# =============================================================================
#  db/queue_store.py — SQLite-backed persistent upload queue
#
#  This is a transient queue, NOT an event log.
#  - Rows are deleted immediately on successful upload
#  - Failed rows are purged after UPLOAD_FAILED_RETENTION_SECONDS
#  - Under normal operation the table is nearly empty
#
#  Job lifecycle:
#
#       capture → INSERT (pending)
#                     │
#                     ▼
#               worker picks up → UPDATE (uploading)
#                     │
#           ┌─────────┴──────────┐
#      success                 failure
#           │                    │
#      DELETE row          UPDATE attempts++
#                               │
#                    max retries reached?
#                    ┌───────────┴───────────┐
#                   yes                      no
#                    │                        │
#             UPDATE (failed)         stays (uploading→pending)
#             purged after                retry later
#             retention period
# =============================================================================

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import List, Optional

import config
from utils import get_logger

log = get_logger(__name__)

# Job status constants
STATUS_PENDING    = "pending"
STATUS_UPLOADING  = "uploading"
STATUS_DONE       = "done"
STATUS_FAILED     = "failed"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS upload_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath      TEXT    NOT NULL,
    metadata_json TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    attempts      INTEGER NOT NULL DEFAULT 0,
    created_at    REAL    NOT NULL,
    updated_at    REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_status ON upload_jobs(status);
CREATE INDEX IF NOT EXISTS idx_updated_at ON upload_jobs(updated_at);
"""


class QueueStore:
    """
    Thread-safe SQLite queue for upload jobs.

    claim_next() uses an application-level lock to make its SELECT+UPDATE
    atomic. All other methods rely on SQLite WAL mode for safe concurrent
    access — single-statement operations are atomic at the database level
    and do not require an additional application lock.
    """

    def __init__(self, db_path: str = config.DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()
        self._recover_interrupted()
        self._purge_failed()
        log.info("QueueStore ready at %s", db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, filepath: str, metadata_json: str) -> int:
        """Insert a new pending job. Returns the new row id."""
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO upload_jobs (filepath, metadata_json, status, attempts, created_at, updated_at) "
                "VALUES (?, ?, ?, 0, ?, ?)",
                (filepath, metadata_json, STATUS_PENDING, now, now),
            )
            row_id = cur.lastrowid
        log.debug("Enqueued job #%d: %s", row_id, os.path.basename(filepath))
        return row_id

    def claim_next(self) -> Optional[dict]:
        """
        Atomically claim the next pending job for uploading.
        Returns a dict with job data, or None if the queue is empty.
        """
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, filepath, metadata_json, attempts FROM upload_jobs "
                    "WHERE status = ? ORDER BY updated_at ASC LIMIT 1",
                    (STATUS_PENDING,),
                ).fetchone()

                if row is None:
                    return None

                conn.execute(
                    "UPDATE upload_jobs SET status = ?, updated_at = ? WHERE id = ?",
                    (STATUS_UPLOADING, now, row["id"]),
                )

        return dict(row)

    def mark_done(self, job_id: int) -> None:
        """Delete the job row immediately — it has been successfully uploaded."""
        with self._connect() as conn:
            conn.execute("DELETE FROM upload_jobs WHERE id = ?", (job_id,))
        log.debug("Job #%d marked done and removed from queue", job_id)

    def release_to_pending(self, job_id: int) -> None:
        """
        Return a claimed job back to pending WITHOUT incrementing the attempt
        counter.  Use this exclusively for transient offline situations where
        no upload was attempted — the job should not be penalised for a
        network outage.
        """
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE upload_jobs SET status = ?, updated_at = ? WHERE id = ?",
                (STATUS_PENDING, now, job_id),
            )
        log.debug("Job #%d released back to pending (no attempt counted)", job_id)

    def mark_failed_attempt(self, job_id: int) -> bool:
        """
        Increment the attempt counter.
        - If under the retry limit: reset to pending so the worker retries it.
        - If at/over the limit: mark as failed (will be purged after retention).
        Returns True if the job will be retried, False if it's been failed out.
        """
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT attempts FROM upload_jobs WHERE id = ?", (job_id,)
            ).fetchone()

            if row is None:
                return False

            new_attempts = row["attempts"] + 1

            if new_attempts >= config.UPLOAD_MAX_RETRIES:
                conn.execute(
                    "UPDATE upload_jobs SET status = ?, attempts = ?, updated_at = ? WHERE id = ?",
                    (STATUS_FAILED, new_attempts, now, job_id),
                )
                log.warning(
                    "Job #%d permanently failed after %d attempts", job_id, new_attempts
                )
                return False
            else:
                conn.execute(
                    "UPDATE upload_jobs SET status = ?, attempts = ?, updated_at = ? WHERE id = ?",
                    (STATUS_PENDING, new_attempts, now, job_id),
                )
                log.debug(
                    "Job #%d attempt %d/%d failed — back to pending",
                    job_id, new_attempts, config.UPLOAD_MAX_RETRIES,
                )
                return True

    def pending_count(self) -> int:
        """Return number of jobs waiting to be uploaded."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM upload_jobs WHERE status IN (?, ?)",
                (STATUS_PENDING, STATUS_UPLOADING),
            ).fetchone()
        return row[0] if row else 0

    def purge_failed(self) -> None:
        """Remove failed rows that have exceeded the retention window."""
        self._purge_failed()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # allows concurrent readers
        conn.execute("PRAGMA synchronous=NORMAL") # safe and faster than FULL
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _recover_interrupted(self) -> None:
        """
        On startup, any job stuck in 'uploading' was interrupted mid-flight
        (e.g. power loss). Reset them to 'pending' so they are retried.
        """
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE upload_jobs SET status = ?, updated_at = ? WHERE status = ?",
                (STATUS_PENDING, now, STATUS_UPLOADING),
            )
            if cur.rowcount:
                log.info(
                    "Recovered %d interrupted upload job(s) → pending", cur.rowcount
                )

    def _purge_failed(self) -> None:
        """Delete failed rows older than the configured retention window."""
        cutoff = time.time() - config.UPLOAD_FAILED_RETENTION_SECONDS
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM upload_jobs WHERE status = ? AND updated_at < ?",
                (STATUS_FAILED, cutoff),
            )
            if cur.rowcount:
                log.info("Purged %d expired failed job(s) from queue", cur.rowcount)
