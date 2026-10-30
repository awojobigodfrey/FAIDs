from fastapi import APIRouter, HTTPException, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from services.database import db_service
from services.detection import detection_service
from models.schemas import PushSubscriptionCreate
from typing import List, Dict
import asyncio
import json
import uuid

router = APIRouter()

# Queue to hold manual capture commands for the Pi
capture_trigger = asyncio.Queue()

# Track active Pi SSE connections
active_pi_connections = 0

@router.get("/events")
async def get_events(limit: int = 100) -> List[Dict]:
    return await db_service.get_all_events(limit=limit)

@router.get("/intrusions")
async def get_intrusions(limit: int = 50) -> List[Dict]:
    return await db_service.get_intrusions(limit=limit)

@router.get("/recognized")
async def get_recognized(limit: int = 50) -> List[Dict]:
    return await db_service.get_recognized(limit=limit)

@router.get("/stats")
async def get_stats() -> Dict:
    return await db_service.get_stats()

@router.post("/subscribe")
async def subscribe_push(sub: PushSubscriptionCreate):
    """Endpoint for frontend to register a Push Subscription"""
    success = await db_service.save_subscription(sub)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to save subscription")

# --- NEW PI EDGE ENDPOINTS ---

@router.post("/detect")
async def detect_intrusion(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Endpoint for the Raspberry Pi to upload an image.
    Classifies the image and stores it if a person or intrusion is detected.
    """
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        image_bytes = await file.read()
        result = await detection_service.process_and_store_image(image_bytes, background_tasks)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@router.get("/pi/status")
async def get_pi_status():
    """Returns whether the Pi is currently connected and listening for commands"""
    return {"online": active_pi_connections > 0, "connections": active_pi_connections}

@router.post("/pi/capture")
async def trigger_pi_capture(camera_id: int = 0):
    """Frontend calls this to tell the Pi to capture an image"""
    
    # 1. Build the exact JSON dictionary the Pi is looking for!
    command_data = {
        "id": str(uuid.uuid4()),
        "type": "capture",
        "payload": {"camera_id": camera_id}
    }
    
    # 2. Send it into the queue
    await capture_trigger.put(json.dumps(command_data))
    return {"status": "triggered", "message": "Capture command sent to Pi"}

@router.get("/pi/stream")
async def pi_stream(request: Request):
    """SSE endpoint for the Pi to listen for commands"""
    async def event_generator():
        global active_pi_connections
        active_pi_connections += 1
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait for a command, timeout every 2 seconds to check disconnects
                    msg = await asyncio.wait_for(capture_trigger.get(), timeout=2.0)
                    
                    # 3. Add the required "event: command" header the Pi expects
                    yield f"event: command\ndata: {msg}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive to prevent connection drop
                    yield ": keep-alive\n\n"
        finally:
            active_pi_connections -= 1

    return StreamingResponse(event_generator(), media_type="text/event-stream")