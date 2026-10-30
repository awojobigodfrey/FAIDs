from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from models.schemas import EventCreate, Event, PushSubscriptionCreate
from typing import List, Dict, Optional
from datetime import datetime

class DatabaseService:
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    async def save_event(self, event: EventCreate) -> Optional[str]:
        try:
            data = {
                "event_type": event.event_type,
                "reason": event.reason,
                "person_name": event.person_name,
                "image_url": event.image_url,
                "confidence": event.confidence,
                "timestamp": event.timestamp.isoformat()
            }

            result = self.client.table("events").insert(data).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]["id"]
            return None
        except Exception as e:
            print(f"Error saving event to database: {e}")
            return None

    async def get_all_events(self, limit: int = 100) -> List[Dict]:
        try:
            result = self.client.table("events").select("*").order("timestamp", desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []

    async def get_intrusions(self, limit: int = 50) -> List[Dict]:
        try:
            result = self.client.table("events").select("*").eq("event_type", "intrusion").order("timestamp", desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching intrusions: {e}")
            return []

    async def get_recognized(self, limit: int = 50) -> List[Dict]:
        try:
            result = self.client.table("events").select("*").eq("event_type", "recognized").order("timestamp", desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching recognized events: {e}")
            return []

    async def get_stats(self) -> Dict:
        try:
            intrusions_result = self.client.table("events").select("id", count="exact").eq("event_type", "intrusion").execute()
            recognized_result = self.client.table("events").select("id", count="exact").eq("event_type", "recognized").execute()

            total_intrusions = intrusions_result.count if intrusions_result.count else 0
            total_recognized = recognized_result.count if recognized_result.count else 0

            return {
                "total_intrusions": total_intrusions,
                "total_recognized": total_recognized
            }
        except Exception as e:
            print(f"Error fetching stats: {e}")
            return {
                "total_intrusions": 0,
                "total_recognized": 0
            }

    async def save_subscription(self, sub: PushSubscriptionCreate) -> bool:
        try:
            data = {
                "endpoint": sub.endpoint,
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
            # Upsert by endpoint to avoid duplicates
            self.client.table("push_subscriptions").upsert(data, on_conflict="endpoint").execute()
            return True
        except Exception as e:
            print(f"Error saving subscription: {e}")
            return False

    async def get_all_subscriptions(self) -> List[Dict]:
        try:
            result = self.client.table("push_subscriptions").select("*").execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error fetching subscriptions: {e}")
            return []

db_service = DatabaseService()
