from azure.storage.blob import BlobServiceClient, ContentSettings
from config import AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER
import io
from datetime import datetime
from typing import Optional
import uuid

class BlobStorageService:
    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        self.container_name = AZURE_STORAGE_CONTAINER
        self._ensure_container_exists()

    def _ensure_container_exists(self):
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container(public_access="blob")
        except Exception as e:
            print(f"Container check/creation error: {e}")

    async def upload_image(self, image_bytes: bytes, event_type: str, reason: str) -> Optional[str]:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            blob_name = f"{event_type}/{reason}_{timestamp}_{unique_id}.jpg"

            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            content_settings = ContentSettings(content_type="image/jpeg")

            blob_client.upload_blob(
                image_bytes,
                overwrite=True,
                content_settings=content_settings
            )

            blob_url = blob_client.url
            return blob_url

        except Exception as e:
            print(f"Error uploading image to blob storage: {e}")
            return None

blob_storage_service = BlobStorageService()
