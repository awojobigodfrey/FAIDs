from azure.ai.vision.face import FaceClient
from azure.ai.vision.face.models import FaceDetectionModel, FaceRecognitionModel
from azure.core.credentials import AzureKeyCredential
from config import AZURE_FACE_ENDPOINT, AZURE_FACE_KEY, AZURE_FACE_PERSON_GROUP_ID
from typing import Optional, Dict
import io

class AzureFaceService:
    def __init__(self):
        if not AZURE_FACE_KEY:
            print("WARNING: AZURE_FACE_KEY not set. Face recognition will not work.")
            self.client = None
            return

        self.client = FaceClient(
            endpoint=AZURE_FACE_ENDPOINT,
            credential=AzureKeyCredential(AZURE_FACE_KEY)
        )
        self.person_group_id = AZURE_FACE_PERSON_GROUP_ID

    async def recognize_face(self, image_bytes: bytes) -> Optional[Dict]:
        if not self.client:
            return {"recognized": False, "reason": "Face API not configured"}

        try:
            detected_faces = self.client.detect(
                image_content=image_bytes,
                detection_model=FaceDetectionModel.DETECTION03,
                recognition_model=FaceRecognitionModel.RECOGNITION04,
                return_face_id=True
            )

            if not detected_faces or len(detected_faces) == 0:
                return {"recognized": False, "reason": "No face detected"}

            face_ids = [face.face_id for face in detected_faces]

            try:
                identify_results = self.client.identify_from_person_group(
                    face_ids=face_ids,
                    person_group_id=self.person_group_id
                )

                if identify_results and len(identify_results) > 0:
                    result = identify_results[0]

                    if result.candidates and len(result.candidates) > 0:
                        candidate = result.candidates[0]

                        person = self.client.person_group.get_person(
                            person_group_id=self.person_group_id,
                            person_id=candidate.person_id
                        )

                        return {
                            "recognized": True,
                            "person_name": person.name,
                            "confidence": candidate.confidence
                        }

            except Exception as identify_error:
                print(f"Face identification error: {identify_error}")
                return {"recognized": False, "reason": "Person group not trained or empty"}

            return {"recognized": False, "reason": "Face not recognized"}

        except Exception as e:
            print(f"Error in face recognition: {e}")
            return {"recognized": False, "reason": f"Error: {str(e)}"}

azure_face_service = AzureFaceService()
