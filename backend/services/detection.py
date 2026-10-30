from datetime import datetime
from services.azure_vision import azure_vision_service
from services.local_vision import local_vision_service
from services.blob_storage import blob_storage_service
from services.database import db_service
from services.notification import notification_service
from services.email import email_service
from models.schemas import EventCreate
import asyncio
from fastapi import BackgroundTasks

class DetectionService:
    async def process_and_store_image(self, image_bytes: bytes, background_tasks: BackgroundTasks = None):
        # 1. Ask Local OpenCV Vision if there is a general human in the image
        local_result = await local_vision_service.detect_person(image_bytes)
        has_human = local_result.get("has_person", True)
        
        if not has_human:
            return {
                "status": "success",
                "message": "No human detected by Local AI",
                "detected": False,
                "Local_status": local_result.get("local_status"),
                "Local_objects_found": local_result.get("local_objects_found", [])
            }
            
        # 2. If human found, ask Azure Custom Vision if they are wearing a mask
        vision_result = await azure_vision_service.classify_mask(image_bytes)

        if vision_result is None:
            return {"status": "error", "message": "Failed to get response from Custom Vision", "detected": False}

        confidence = vision_result.get("confidence", 0.0)
        person_score = vision_result.get("person_score", 0.0)
        mask_score = vision_result.get("mask_score", 0.0)

        # Classification workflow
        if vision_result.get("has_mask", False):
            event_type = "intrusion"
            reason = "mask_detected"
            person_name = None
        else:
            # Google already confirmed it's a person. If there's no mask, they are recognized.
            event_type = "recognized"
            reason = "person_detected"
            person_name = None

        # Upload image to Blob Storage
        image_url = await blob_storage_service.upload_image(image_bytes, event_type, reason)
        
        if image_url:
            # Save metadata to Supabase
            event = EventCreate(
                event_type=event_type,
                reason=reason,
                person_name=person_name,
                image_url=image_url,
                confidence=confidence,
                timestamp=datetime.now()
            )
            await db_service.save_event(event)

            if event_type == "intrusion":
                subs = await db_service.get_all_subscriptions()
                for sub in subs:
                    sub_info = {
                        "endpoint": sub["endpoint"],
                        "keys": {
                            "p256dh": sub["p256dh"],
                            "auth": sub["auth"]
                        }
                    }
                    asyncio.create_task(asyncio.to_thread(
                        notification_service.send_notification,
                        sub_info,
                        {"title": "Intrusion Alert!", "body": f"Motion detected: {reason}"}
                    ))
                    
                if background_tasks:
                    background_tasks.add_task(email_service.send_intrusion_email, reason, image_url)

            return {
                "status": "success", 
                "detected": True, 
                "event_type": event_type, 
                "confidence": confidence,
                "person_score": person_score,
                "mask_score": mask_score,
                "Local_status": local_result.get("local_status"),
                "Local_objects_found": local_result.get("local_objects_found", []),
                "Local_error": local_result.get("local_error", "")
            }

        return {"status": "error", "message": "Failed to upload image"}

detection_service = DetectionService()