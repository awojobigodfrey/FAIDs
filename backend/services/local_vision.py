import cv2
import numpy as np
import os
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
PROTOTXT_PATH = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.prototxt")
MODEL_PATH = os.path.join(MODEL_DIR, "MobileNetSSD_deploy.caffemodel")

# URLs for the pre-trained MobileNet SSD model (trained on VOC)
PROTOTXT_URL = "https://raw.githubusercontent.com/PINTO0309/MobileNet-SSD-RealSense/master/caffemodel/MobileNetSSD/MobileNetSSD_deploy.prototxt"
MODEL_URL = "https://raw.githubusercontent.com/PINTO0309/MobileNet-SSD-RealSense/master/caffemodel/MobileNetSSD/MobileNetSSD_deploy.caffemodel"

class LocalVisionService:
    def __init__(self):
        self.net = None
        self._ensure_models_exist()
        self._load_model()
        
    def _ensure_models_exist(self):
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        if not os.path.exists(PROTOTXT_PATH):
            print("Downloading MobileNetSSD prototxt...")
            urllib.request.urlretrieve(PROTOTXT_URL, PROTOTXT_PATH)
            
        if not os.path.exists(MODEL_PATH):
            print("Downloading MobileNetSSD caffemodel (this may take a few seconds)...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            
    def _load_model(self):
        try:
            self.net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, MODEL_PATH)
            print("Local MobileNet SSD model loaded successfully.")
        except Exception as e:
            print(f"Failed to load OpenCV model: {e}")
            
    async def detect_person(self, image_bytes: bytes) -> dict:
        """
        Runs the image through a local OpenCV MobileNet SSD model to detect humans.
        Returns a dict with 'has_person' and debugging info.
        """
        if self.net is None:
            return {"has_person": True, "local_status": "MODEL_NOT_LOADED"}
            
        try:
            # Convert bytes to numpy array then to OpenCV image
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {"has_person": True, "local_status": "INVALID_IMAGE"}
                
            # Preprocess the image (blobFromImage)
            # MobileNet SSD expects 300x300 images and mean subtraction of 127.5 and scale factor of 0.007843
            blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
            
            # Pass the blob through the network
            self.net.setInput(blob)
            import asyncio
            # Run inference in a thread so it doesn't block the async loop
            detections = await asyncio.to_thread(self.net.forward)
            
            found_person = False
            objects_found = []
            
            # loop over the detections
            for i in np.arange(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                
                # filter out weak detections
                if confidence > 0.4:
                    # extract the index of the class label from the detections
                    idx = int(detections[0, 0, i, 1])
                    
                    # In MobileNet SSD (VOC), class 15 is 'person'
                    if idx == 15:
                        found_person = True
                        objects_found.append(f"person ({confidence:.2f})")
                    elif idx == 12:
                        objects_found.append(f"dog ({confidence:.2f})")
                    elif idx == 8:
                        objects_found.append(f"cat ({confidence:.2f})")
                    else:
                        objects_found.append(f"class_id_{idx} ({confidence:.2f})")
                        
            return {"has_person": found_person, "local_status": "SUCCESS", "local_objects_found": objects_found}
            
        except Exception as e:
            return {"has_person": True, "local_status": f"EXCEPTION_{type(e).__name__}", "local_error": str(e)}

local_vision_service = LocalVisionService()
