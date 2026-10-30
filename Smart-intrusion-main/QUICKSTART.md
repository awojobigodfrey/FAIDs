# Quick Start Guide

Get the Agricultural Intrusion Detection System (Pi-edge edition) running.

## Prerequisites

- Python 3.8+ installed
- Node.js 16+ installed
- A Raspberry Pi (or other device) able to capture images and reach the backend over the network
- Azure Custom Vision project + Blob Storage account, and a Supabase project

## Step 1: Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```env
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_key
VITE_VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
RESEND_API_KEY=your_resend_api_key
RESEND_TO_EMAIL=your_email@example.com
DETECTION_CONFIDENCE_THRESHOLD=0.5
Intrusion_detector=Iteration1
```

The Azure Custom Vision endpoint, prediction key, project ID, and Blob Storage connection string are currently set directly in `backend/config.py`. Update them there with your own values (and move them into `.env` for anything beyond local testing).

## Step 2: Apply the Database Migration

In your Supabase project, run the SQL files in `supabase/migrations/` to create the `events` and `push_subscriptions` tables and their RLS policies.

## Step 3: Start the Backend

```bash
cd backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Step 4: Start the Frontend

Open a new terminal:

```bash
npm install
npm run dev
```

You should see:
```
VITE ready in XXX ms
Local: http://localhost:5173/
```

Before this works end-to-end, set `API_BASE_URL` in `src/services/api.ts` to wherever your backend is actually reachable from the browser (localhost, a LAN IP, or a tunnel URL).

## Step 5: Connect the Raspberry Pi

The Pi is the camera client — it is not part of this repo's `npm`/`pip install` flow, but it talks to two endpoints:

1. **Listen for commands:** open an SSE connection to `GET /api/pi/stream`. When the dashboard's manual-capture button is pressed, the Pi receives:
   ```
   event: command
   data: {"id": "...", "type": "capture", "payload": {"camera_id": 0}}
   ```
2. **Upload a frame:** whenever the Pi captures an image (on a `capture` command, or on its own PIR motion trigger), `POST` the JPEG as `multipart/form-data` under field `file` to:
   ```
   POST /api/detect
   ```

The backend classifies the image, and — if it scores above `DETECTION_CONFIDENCE_THRESHOLD` for `Person` or `Masked` — uploads it to Blob Storage and writes an event to Supabase.

## Step 6: Use the System

1. Open your browser to `http://localhost:5173`.
2. Use the manual capture control to remotely trigger a Pi capture, or just let the Pi capture on its own (e.g. PIR motion).
3. The system will:
   - Classify each uploaded image as `Person` or `Masked`
   - Store `Masked` detections as `intrusion` events
   - Store `Person` detections as `recognized` events
   - Discard anything below the confidence threshold
4. View results live in the dashboard.

## Testing the System

### Test an intrusion event
- Send an image clearly showing a masked person to `POST /api/detect`.
- Should be stored as an `intrusion` event with reason `mask_detected`.

### Test a recognized event
- Send an image clearly showing an unmasked person.
- Should be stored as a `recognized` event with reason `person_detected`.

### Test a no-op
- Send an image with no person in it.
- Should return `{"detected": false}` and nothing should be written to Supabase.

## Dashboard Features

- **Stats Cards**: total intrusion and recognized counts
- **Intrusions Tab**: all flagged events
- **Recognized Tab**: all detected-person events
- **Manual Capture**: remotely trigger the Pi to capture and upload a frame on demand

## API Testing

You can test the API directly with `curl`:

```bash
# Get statistics
curl http://localhost:8000/api/stats

# Get all events
curl http://localhost:8000/api/events

# Get intrusions only
curl http://localhost:8000/api/intrusions

# Get recognized visits only
curl http://localhost:8000/api/recognized

# Trigger a remote Pi capture
curl -X POST "http://localhost:8000/api/pi/capture?camera_id=0"

# Upload an image directly (simulating the Pi)
curl -X POST http://localhost:8000/api/detect -F "file=@test.jpg"
```

## Troubleshooting

### `/api/pi/capture` returns success but the Pi never reacts
- The Pi must already have an open `GET /api/pi/stream` connection — the command queue is in-memory and not persisted, so a disconnected Pi misses the command.

### `/api/detect` returns "Nothing of interest detected" / no events appear
- Lower `DETECTION_CONFIDENCE_THRESHOLD` if your model's confidence scores are coming in below it.
- Confirm `Intrusion_detector` in `.env` matches a published Custom Vision iteration name.

### Frontend can't connect to backend
- Verify the backend is running and reachable at the address set in `API_BASE_URL` (`src/services/api.ts`).
- Check the browser console for CORS or network errors.

### Images not displaying
- Check Azure Blob Storage container permissions (the backend tries to create the container with public blob access on startup).
- Confirm `AZURE_STORAGE_CONNECTION_STRING` in `backend/config.py` is correct.
- Look for upload errors in the backend console.

## Next Steps

- Wire up the unused face-recognition pipeline (`azure_face_unused.py`, `setup_face_api_unused.py`) if you want named-person recognition instead of generic person/mask detection.
- Move all hardcoded Azure credentials in `backend/config.py` into environment variables.
- Deploy the backend somewhere reachable by the Pi over the field network (or a tunnel), and run the Pi capture client as a service.

## Getting Help

Check the main `README.md` for:
- Full architecture explanation
- Complete API documentation
- Project structure
- Security notes
