import os
import json
from pywebpush import webpush, WebPushException

class NotificationService:
    def __init__(self):
        self.vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
        self.vapid_claims = {
            "sub": "mailto:admin@example.com"
        }

    def send_notification(self, subscription_info: dict, payload: dict):
        if not self.vapid_private_key:
            print("VAPID_PRIVATE_KEY not set. Cannot send push notification.")
            return

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
        except WebPushException as ex:
            print(f"Web Push Error: {repr(ex)}")

notification_service = NotificationService()
