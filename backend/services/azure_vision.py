from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from msrest.authentication import ApiKeyCredentials
from config import (
    AZURE_CV_PREDICTION_ENDPOINT,
    AZURE_CV_PREDICTION_KEY,
    AZURE_CV_PROJECT_ID,
    AZURE_CV_PUBLISHED_NAME,
    PERSON_CONFIDENCE_THRESHOLD,
    MASK_CONFIDENCE_THRESHOLD
)
from typing import Optional, Dict
import io

class AzureVisionService:
    """
    Azure Custom Vision Classification service
    Tags used in the model:
      - Person
      - Masked
    """

    def __init__(self):
        credentials = ApiKeyCredentials(in_headers={"Prediction-key": AZURE_CV_PREDICTION_KEY})
        self.predictor = CustomVisionPredictionClient(AZURE_CV_PREDICTION_ENDPOINT, credentials)
        self.project_id = AZURE_CV_PROJECT_ID
        self.published_name = AZURE_CV_PUBLISHED_NAME

    async def classify_mask(self, image_bytes: bytes) -> Optional[Dict]:
        """
        Classifies an image to determine:
          - if a person is present
          - if the person is wearing a mask
        """
        try:
            image_stream = io.BytesIO(image_bytes)
            results = self.predictor.classify_image(
                self.project_id,
                self.published_name,
                image_stream
            )

            if not results.predictions:
                return None

            person_score = 0.0
            mask_score = 0.0
            best_confidence = 0.0
            best_tag = None

            for prediction in results.predictions:
                tag = prediction.tag_name.lower()
                confidence = prediction.probability

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_tag = prediction.tag_name

                if tag == "person":
                    person_score = max(person_score, confidence)
                elif tag == "masked":
                    mask_score = max(mask_score, confidence)

            has_person = person_score >= PERSON_CONFIDENCE_THRESHOLD
            has_mask = mask_score >= MASK_CONFIDENCE_THRESHOLD

            return {
                "has_person": has_person,
                "has_mask": has_mask,
                "person_score": person_score,
                "mask_score": mask_score,
                "confidence": best_confidence,
                "tag": best_tag
            }

        except Exception as e:
            print(f"Error in Custom Vision classification: {e}")
            return None

# Create a single instance to be imported elsewhere
azure_vision_service = AzureVisionService()
