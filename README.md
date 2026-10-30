# Agricultural Intrusion Detection System

A real-time intrusion detection system that pairs a Raspberry Pi camera edge device with Azure AI Custom Vision and a web dashboard. The Pi captures images (on motion or by remote command), the backend classifies them, and confirmed events are stored with their image and shown live on the dashboard.

## System Overview

- The **Raspberry Pi** captures images locally (e.g. on PIR motion) and uploads them to the backend, or waits for a manual capture command pushed from the dashboard.
- The **backend (FastAPI)** classifies each image with Azure Custom Vision, decides whether it's a `recognized` (person present) or `intrusion` (mask detected) event, uploads the image to Azure Blob Storage, writes the event to Supabase, and dispatches **Web Push Notifications** for intrusions.
- The **dashboard (React)** displays live stats and event history, can remotely trigger a Pi capture, and allows users to subscribe to push notifications.

## Architecture

```
Raspberry Pi (camera + PIR)
   │  captures image
   ▼
POST /api/detect ───────────► Backend (FastAPI)
                                   │
                                   ├─► Azure Custom Vision (classification)
                                   ├─► Azure Blob Storage (image upload)
                                   └─► Supabase (event metadata)

Dashboard (React) ──POST /api/pi/capture──► capture command queue
Raspberry Pi ◄──GET /api/pi/stream (SSE)──┘  (Pi listens for "capture" commands)

Dashboard (React) ──GET /api/events, /intrusions, /recognized, /stats──► Backend
```

### Detection logic

The backend classifies each uploaded image with a single Azure Custom Vision model (tags: `Person`, `Masked`):

| Custom Vision result        | Event type   | Reason          |
|------------------------------|--------------|-----------------|
| `Masked` tag above threshold | `intrusion`  | `mask_detected` |
| `Person` tag above threshold | `recognized` | `person_detected` |
| Neither tag above threshold  | (ignored, not stored) | — |

Every stored event is uploaded to Azure Blob Storage and written to the Supabase `events` table.

## Prerequisites

### Backend
- Python 3.8+
- An Azure Custom Vision project with a published iteration trained on `Person` / `Masked` tags
- Azure Blob Storage account
- Supabase project (for event storage)

### Pi edge device
- Raspberry Pi with a USB or Pi Camera
- Network access to the backend's `/api/detect` and `/api/pi/stream` endpoints

### Frontend
- Node.js 16+
- npm

## Setup Instructions

### 1. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env` with your credentials (the Azure Custom Vision keys currently live directly in `config.py` — for any real deployment, move them into environment variables instead):

```env
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_or_service_key
VITE_VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
RESEND_API_KEY=your_resend_api_key
RESEND_TO_EMAIL=your_email@example.com
AZURE_FACE_KEY=                       # unused in the current detection flow, reserved for future face recognition
AZURE_FACE_PERSON_GROUP_ID=agricultural-workers
DETECTION_CONFIDENCE_THRESHOLD=0.5
Intrusion_detector=Iteration1         # Custom Vision published iteration name
```

> **Note:** `backend/services/azure_face_unused.py` and `backend/setup_face_api_unused.py` contain a named-face-recognition pipeline that is not currently wired into `/api/detect`. The live detection flow only distinguishes "person" vs "masked person." They're kept in the repo for a future iteration.

### 2. Supabase Setup

Run the migrations in `supabase/migrations/` against your Supabase project to create the `events` and `push_subscriptions` tables, row-level security policies, and indexes.

### 3. Frontend Setup

```bash
npm install
```

Update the `API_BASE_URL` constant in `src/services/api.ts` to point at wherever your backend is reachable (a tunnel URL, your Pi/server's LAN IP, etc).

### 4. Running the System

**Terminal 1 — Backend:**
```bash
cd backend
python main.py
```

**Terminal 2 — Frontend:**
```bash
npm run dev
```

The backend API is available at `http://localhost:8000`.
The frontend dashboard is available at `http://localhost:5173`.

**On the Raspberry Pi:** run your capture client (PIR-triggered or scheduled) so it:
1. Listens on `GET /api/pi/stream` (Server-Sent Events) for `event: command` messages with `{"type": "capture", "payload": {"camera_id": N}}`.
2. Captures a frame and `POST`s it as multipart form data to `/api/detect`.

## Usage

1. Open the dashboard in your browser.
2. Use the manual capture control to trigger a Pi capture on demand, or let the Pi capture autonomously on motion.
3. Confirmed detections appear in the dashboard's Intrusions / Recognized tabs along with the captured image and confidence score.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/events?limit=` | All events, most recent first |
| GET | `/api/intrusions?limit=` | Intrusion events only |
| GET | `/api/recognized?limit=` | Recognized events only |
| GET | `/api/stats` | Total intrusion / recognized counts |
| POST | `/api/detect` | Pi uploads an image (`multipart/form-data`, field `file`) for classification |
| POST | `/api/pi/capture?camera_id=` | Dashboard triggers a remote Pi capture |
| GET | `/api/pi/stream` | SSE stream the Pi listens on for capture commands |
| GET | `/api/pi/status` | Returns whether the Pi is currently online/listening |

## Configuration

### Backend Environment Variables (`backend/.env`)

- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — Supabase project credentials
- `AZURE_FACE_KEY` / `AZURE_FACE_PERSON_GROUP_ID` — reserved for the not-yet-integrated face recognition pipeline
- `Intrusion_detector` — Custom Vision published iteration name (default: `Iteration1`)
- `DETECTION_CONFIDENCE_THRESHOLD` — minimum confidence to act on a tag (default: `0.5`)

The Azure Custom Vision endpoint/key and Blob Storage connection string are currently hardcoded in `backend/config.py`. Move these to environment variables before deploying anywhere outside a local/dev setup.

## Project Structure

```
├── backend/
│   ├── main.py                       # FastAPI app entrypoint
│   ├── config.py                     # Configuration / credentials
│   ├── requirements.txt              # Python dependencies
│   ├── services/
│   │   ├── azure_vision.py           # Azure Custom Vision classification client
│   │   ├── azure_face_unused.py      # Reserved face-recognition pipeline (not wired in)
│   │   ├── blob_storage.py           # Azure Blob Storage upload
│   │   ├── database.py               # Supabase client / event queries
│   │   └── detection.py              # Orchestrates classify → upload → store
│   ├── models/
│   │   └── schemas.py                # Pydantic models
│   ├── api/
│   │   └── routes.py                 # /api routes incl. Pi capture/stream/detect
│   ├── utils/
│   │   └── helpers.py                # Image resize/validation helpers
│   └── setup_face_api_unused.py      # CLI for the reserved face pipeline
├── src/
│   ├── App.tsx                       # Main dashboard component
│   ├── types.ts                      # TypeScript types
│   ├── components/
│   │   ├── StatCard.tsx
│   │   └── EventCard.tsx
│   ├── services/
│   │   └── api.ts                    # API client (events, stats, Pi capture trigger)
│   └── utils/
│       └── date.ts
├── supabase/
│   └── migrations/                   # events table schema + RLS policies
└── README.md
```

## Troubleshooting

### Pi never captures / dashboard trigger does nothing
- Confirm the Pi has an active connection open to `GET /api/pi/stream`.
- The capture queue only holds commands in memory — if the Pi isn't currently listening when a trigger is sent, that command is lost.

### No events showing up
- Check the backend logs for Custom Vision or Blob Storage errors when `/api/detect` is hit.
- Verify the Custom Vision iteration is published and `Intrusion_detector` matches its name.
- Confirm `DETECTION_CONFIDENCE_THRESHOLD` isn't set so high that valid detections are being discarded.

### Images not displaying on the dashboard
- Verify the Blob Storage container exists and allows public blob access (the backend tries to create it with `public_access="blob"` on startup).
- Check that `image_url` values returned by Supabase are reachable from your browser.

### Frontend can't reach the backend
- Confirm `API_BASE_URL` in `src/services/api.ts` matches where the backend is actually running/exposed.
- Check for CORS errors in the browser console (CORS is currently wide open via `allow_origins=["*"]`).

## Security Notes

- This system has no authentication on the API or dashboard (demo/educational purposes).
- Azure Custom Vision keys and the Blob Storage connection string are currently committed in `backend/config.py` — rotate them and move to environment variables before any real deployment.
- Do not expose the backend API directly to the public internet without adding auth in front of it.

## License

This project is for educational and demonstration purposes.
