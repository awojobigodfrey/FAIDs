# =============================================================================
#  config.py — Central configuration for the Agri-IDS hardware node
#  Edit this file to match your wiring and backend API deployment.
# =============================================================================

import os
from typing import List

# ---------------------------------------------------------------------------
# GPIO Pin assignments  (BCM numbering)
# ---------------------------------------------------------------------------
PIR_PINS: List[int] = [17, 27]          # PIR sensor 1 → GPIO17, sensor 2 → GPIO27

# ---------------------------------------------------------------------------
# Camera indices (OpenCV VideoCapture index)
# ---------------------------------------------------------------------------
CAMERA_INDICES: List[int] = [0, 2]      # /dev/video0, /dev/video2

# Camera capture resolution
CAMERA_WIDTH: int  = 1280
CAMERA_HEIGHT: int = 720

# How long (seconds) to keep a camera open after the last capture before
# releasing it, to avoid hammering USB bandwidth.
CAMERA_RELEASE_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# PIR / Motion detection behaviour
# ---------------------------------------------------------------------------
# Minimum seconds between two consecutive PIR-triggered captures on the
# same sensor (debounce / cooldown).
PIR_COOLDOWN_SECONDS: int = 10

# ---------------------------------------------------------------------------
# LED Behaviour
# ---------------------------------------------------------------------------
LED_PIN: int = 22
LED_BLINK_DURATION: int = 3

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("AGRI_IDS_API_URL", "https://vigilant-space-telegram-9wjjr7pj6wxc6w-8000.app.github.dev/api")
API_KEY: str      = os.getenv("AGRI_IDS_API_KEY",  "REPLACE_ME")

# Node identity — helps the backend distinguish multiple deployed units
NODE_ID: str = os.getenv("AGRI_IDS_NODE_ID", "node-001")

# Endpoints (relative to API_BASE_URL)
ENDPOINT_EVENT_UPLOAD: str = "/detect"          # POST — upload image + metadata
ENDPOINT_SSE_STREAM:   str = "/pi/stream"   # GET  — SSE command stream
ENDPOINT_ACK_COMMAND:  str = "/commands/{id}/ack" # POST — acknowledge a command

# Request timeout for regular HTTP calls (connect_timeout, read_timeout)
REQUEST_TIMEOUT: tuple = (5, 15)

# SSE stream read timeout — how long to wait for the next event before
# treating the connection as stale and reconnecting.
SSE_READ_TIMEOUT: int = 60  # seconds

# ---------------------------------------------------------------------------
# SSE reconnection backoff
# ---------------------------------------------------------------------------
SSE_RECONNECT_BASE_DELAY: float = 2.0   # Initial delay (seconds) after a disconnect
SSE_RECONNECT_MAX_DELAY:  float = 30.0  # Cap on reconnect delay (seconds)
SSE_RECONNECT_BACKOFF_FACTOR: float = 2.0  # Multiplier applied on each failure

# ---------------------------------------------------------------------------
# Upload — persistent queue & retry
# ---------------------------------------------------------------------------
UPLOAD_MAX_RETRIES: int = 5         # Attempts before a job is marked failed

# Exponential backoff for upload retries (also used when offline)
UPLOAD_BACKOFF_BASE:   float = 2.0  # seconds for first retry
UPLOAD_BACKOFF_MAX:    float = 300.0  # cap at 5 minutes between retries
UPLOAD_BACKOFF_FACTOR: float = 2.0  # multiplier per attempt

# How long (seconds) to keep failed job rows before purging them from the DB.
# Done rows are deleted immediately on success.
UPLOAD_FAILED_RETENTION_SECONDS: int = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Image storage (local buffer before upload)
# ---------------------------------------------------------------------------
IMAGE_SAVE_DIR: str = os.getenv("AGRI_IDS_IMAGE_DIR", "/tmp/agri_ids/captures")

# If True, keep a local JPEG copy after a successful upload
KEEP_LOCAL_COPY: bool = False

# JPEG quality for saved captures (0-100)
JPEG_QUALITY: int = 85

# ---------------------------------------------------------------------------
# SQLite persistent queue
# ---------------------------------------------------------------------------
DB_PATH: str = os.getenv("AGRI_IDS_DB_PATH", "/var/lib/agri_ids/queue.db")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str        = os.getenv("AGRI_IDS_LOG_LEVEL", "INFO")
LOG_FILE: str         = "/var/log/agri_ids.log"   # set "" to disable file logging
LOG_MAX_BYTES: int    = 5 * 1024 * 1024            # 5 MB per file
LOG_BACKUP_COUNT: int = 3
