# Agricultural Intrusion Detection System - Backend

Python FastAPI backend for the intrusion detection system using Azure AI services.

## Setup

### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `backend/.env` and add your Azure Face API key:

```
AZURE_FACE_KEY=your_actual_face_api_key_here
```

### 3. Run the Backend Server

```bash
cd backend
python main.py
```

The API will start at `http://localhost:8000`

## API Endpoints

- `GET /api/events` - Get all events
- `GET /api/intrusions` - Get intrusion events
- `GET /api/recognized` - Get recognized face events
- `GET /api/stats` - Get statistics (total counts)
- `POST /api/camera/start` - Start camera monitoring
- `POST /api/camera/stop` - Stop camera monitoring
- `GET /api/camera/status` - Check camera status

## Camera Monitoring

The system captures frames from your webcam every 5 seconds (configurable via `CAPTURE_INTERVAL`).

Each frame is:
1. Sent to Azure Custom Vision for mask detection
2. If no mask, sent to Azure Face API for recognition
3. Classified as intrusion or recognized
4. Uploaded to Azure Blob Storage
5. Saved to Supabase database

## Azure Face API Setup

You need to create a Person Group and add known faces:

### Create Person Group (one-time setup)

```python
from azure.ai.vision.face import FaceAdministrationClient
from azure.core.credentials import AzureKeyCredential

client = FaceAdministrationClient(
    endpoint="https://azurecustomviz.cognitiveservices.azure.com/",
    credential=AzureKeyCredential("YOUR_KEY")
)

client.person_group.create(
    person_group_id="agricultural-workers",
    name="Agricultural Workers",
    recognition_model="recognition_04"
)
```

### Add a Person

```python
person = client.person_group.create_person(
    person_group_id="agricultural-workers",
    name="John Doe"
)

with open("john_face.jpg", "rb") as image:
    client.person_group.add_face(
        person_group_id="agricultural-workers",
        person_id=person.person_id,
        image_content=image.read()
    )
```

### Train Person Group

```python
client.person_group.train(person_group_id="agricultural-workers")
```

## Notes

- The system requires a webcam
- Azure Custom Vision project must be trained with "person_with_mask" and "person_without_mask" tags
- Face recognition requires at least one trained person in the Person Group
