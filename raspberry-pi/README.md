# Agri-IDS — Smart IoT Agricultural Intrusion Detection System
### Hardware Node (Raspberry Pi 3B)

---

## Hardware

| Component       | Connection                          | Config key           |
|-----------------|-------------------------------------|----------------------|
| PIR Sensor 1    | GPIO **17** (BCM) + 5 V + GND    | `PIR_PINS[0]`        |
| PIR Sensor 2    | GPIO **27** (BCM) + 5 V + GND    | `PIR_PINS[1]`        |
| LED             |GPIO **22** (BCM) + 5 V + GND      | `RELAY_PIN`          |
| USB Camera 1    | USB port → `/dev/video0`            | `CAMERA_INDICES[0]`  |
| USB Camera 2    | USB port → `/dev/video2`            | `CAMERA_INDICES[2]`  |

> **PIR wiring**: VCC → 5 V, GND → GND, OUT → GPIO pin.  
> **LED wiring**: VCC → 5 V, GND → GND, IN → GPIO 22.  

---

## Project Structure

```
agri_ids/
├── main.py                     # Entry point — boots everything
├── config.py                   # All tunable settings in one place
├── requirements.txt
├── agri_ids.service            # systemd unit for auto-start on boot
│
├── sensors/
│   ├── pir.py                  # PIR monitoring thread + debounce
│   └── camera.py               # Thread-safe USB camera capture manager
│
├── actuators/
│   └── led.py                # Relay driver with safety timer
│
├── api/
│   ├── uploader.py             # Background upload queue → POST /events
│   └── command_listener.py     # Polls GET /commands/pending, ACKs commands
│
├── core/
│   ├── event_handler.py        # PIR → Camera → Upload pipeline
│   └── command_processor.py    # API command payload → hardware action
│
└── utils/
    └── logger.py               # Rotating file + console logger
```

---

## System Flow

```
PIR Sensor fires
      │
      ▼
 EventHandler.on_pir_motion(sensor_id)
      │
      ├─► CameraManager.capture_image(camera_id)  ──► JPEG saved to disk
      │
      └─► EventUploader.enqueue(filepath, metadata)
                │
                └─► POST /events  { file: JPEG, metadata: JSON }


API Backend pushes command
      │
      ▼
 CommandListener polls GET /commands/pending
      │
      ├─► type="capture"   → CameraManager.capture_image → upload
      │
      └─► POST /commands/{id}/ack
```

---

## API Contract

### Event Upload
```
POST /events
Headers:
    X-API-Key: <key>
    X-Node-ID: <node_id>
Body (multipart/form-data):
    file     : <JPEG image>
    metadata : <JSON string>

Metadata fields:
    node_id    : str    — e.g. "node-001"
    camera_id  : int    — 0 or 1
    sensor_id  : int|null — which PIR fired (null for remote capture)
    reason     : str    — "pir_trigger" | "remote_command"
    timestamp  : str    — ISO-8601 UTC
    resolution : str    — "1280x720"

Response 200:
    { "event_id": "<uuid>" }
```

### Command Poll
```
GET /commands/pending?node_id=<node_id>
Headers:
    X-API-Key: <key>
    X-Node-ID: <node_id>

Response 200:
    [
      {
        "id": "<uuid>",
        "type": "capture",
        "payload": { ... }
      }
    ]

Command payloads:
    capture  : { "camera_id": 0 }
```

### Command Acknowledge
```
POST /commands/{id}/ack
Body (JSON):
    { "success": true }
    { "success": false, "error": "<message>" }
```

---

## Installation

### 1. Clone and install dependencies
```bash
git clone <repo> /opt/agri_ids
cd /opt/agri_ids
pip install -r requirements.txt
```

### 2. Configure
```bash
# Edit config.py directly, or use environment variables:
export AGRI_IDS_API_URL="https://your-api.example.com/api/v1"
export AGRI_IDS_API_KEY="your-secret-key"
export AGRI_IDS_NODE_ID="node-001"
```

### 3. Create the image capture directory
```bash
sudo mkdir -p /tmp/agri_ids/captures
```

### 4. Run manually
```bash
sudo python3 main.py
```

### 5. Install as a system service
```bash
sudo cp agri_ids.service /etc/systemd/system/
# Edit the Environment= lines in the service file first!
sudo systemctl daemon-reload
sudo systemctl enable agri_ids
sudo systemctl start agri_ids

# Check status
sudo systemctl status agri_ids
sudo journalctl -u agri_ids -f
```

---

## Key Configuration Options (`config.py`)

| Variable                    | Default   | Description                                      |
|-----------------------------|-----------|--------------------------------------------------|
| `PIR_PINS`                  | [17, 27]  | BCM GPIO pins for the two PIR sensors            |
| `RELAY_PIN`                 | 22        | BCM GPIO pin for the relay                       |
| `RELAY_ACTIVE_HIGH`         | True      | Set False for active-LOW relay boards            |
| `PIR_COOLDOWN_SECONDS`      | 10        | Min seconds between consecutive PIR captures     |
| `CAMERA_WIDTH/HEIGHT`       | 1280×720  | Capture resolution                               |
| `CAMERA_RELEASE_TIMEOUT`    | 30        | Seconds of idle before camera is released        |
| `COMMAND_POLL_INTERVAL_SECONDS` | 5     | How often to poll the API for commands           |
| `UPLOAD_MAX_RETRIES`        | 3         | Upload retry attempts before giving up           |
| `KEEP_LOCAL_COPY`           | False     | Keep local JPEG after successful upload          |
| `JPEG_QUALITY`              | 85        | JPEG compression quality (0–100)                 |

---

## Notes

- The system is **stateless** between restarts — no local database is used.
- The upload queue is **in-memory only**; images queued at shutdown are lost if not yet uploaded. Set `KEEP_LOCAL_COPY = True` and implement a startup resend mechanism if this matters for your deployment.
- Cameras are opened **lazily** and auto-released after `CAMERA_RELEASE_TIMEOUT` seconds of inactivity to save USB bandwidth.
- PIR debounce (`PIR_COOLDOWN_SECONDS`) prevents event floods on sustained motion.
