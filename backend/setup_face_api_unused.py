import os
import sys
import time
from azure.ai.vision.face import FaceAdministrationClient
from azure.core.credentials import AzureKeyCredential
from config import AZURE_FACE_ENDPOINT, AZURE_FACE_KEY, AZURE_FACE_PERSON_GROUP_ID

def setup_person_group():
    if not AZURE_FACE_KEY:
        print("Error: AZURE_FACE_KEY not set in .env file")
        return False

    print(f"Setting up Face API Person Group: {AZURE_FACE_PERSON_GROUP_ID}")
    print(f"Endpoint: {AZURE_FACE_ENDPOINT}")

    try:
        client = FaceAdministrationClient(
            endpoint=AZURE_FACE_ENDPOINT,
            credential=AzureKeyCredential(AZURE_FACE_KEY)
        )

        print("\n1. Creating Person Group...")
        try:
            client.person_group.create(
                person_group_id=AZURE_FACE_PERSON_GROUP_ID,
                name="Agricultural Workers",
                recognition_model="recognition_04"
            )
            print(f"   ✓ Person Group '{AZURE_FACE_PERSON_GROUP_ID}' created successfully")
        except Exception as e:
            if "PersonGroupExists" in str(e):
                print(f"   ℹ Person Group already exists")
            else:
                print(f"   ✗ Error creating person group: {e}")
                return False

        print("\n2. Person Group is ready!")
        print("\nNext steps:")
        print("- Use add_person() to add known people")
        print("- Use train_person_group() to train the model after adding people")

        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

def add_person(name: str, image_path: str):
    if not AZURE_FACE_KEY:
        print("Error: AZURE_FACE_KEY not set in .env file")
        return None

    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        return None

    try:
        client = FaceAdministrationClient(
            endpoint=AZURE_FACE_ENDPOINT,
            credential=AzureKeyCredential(AZURE_FACE_KEY)
        )

        print(f"\nAdding person: {name}")
        print(f"Image: {image_path}")

        person = client.person_group.create_person(
            person_group_id=AZURE_FACE_PERSON_GROUP_ID,
            name=name
        )
        print(f"   ✓ Person created with ID: {person.person_id}")

        with open(image_path, "rb") as image:
            face = client.person_group.add_face(
                person_group_id=AZURE_FACE_PERSON_GROUP_ID,
                person_id=person.person_id,
                image_content=image.read()
            )
            print(f"   ✓ Face added with ID: {face.persisted_face_id}")

        print(f"\n✓ Successfully added {name} to Person Group")
        print("Remember to train the Person Group after adding all people!")

        return person.person_id

    except Exception as e:
        print(f"Error adding person: {e}")
        return None

def train_person_group():
    if not AZURE_FACE_KEY:
        print("Error: AZURE_FACE_KEY not set in .env file")
        return False

    try:
        client = FaceAdministrationClient(
            endpoint=AZURE_FACE_ENDPOINT,
            credential=AzureKeyCredential(AZURE_FACE_KEY)
        )

        print("\nStarting Person Group training...")
        client.person_group.train(person_group_id=AZURE_FACE_PERSON_GROUP_ID)

        print("Training in progress...\n")
        while True:
            status = client.person_group.get_training_status(
                person_group_id=AZURE_FACE_PERSON_GROUP_ID
            )

            if status.status == "succeeded":
                print("✓ Training succeeded!")
                return True
            elif status.status == "failed":
                print(f"✗ Training failed: {status.message}")
                return False

            print("   Training...")
            time.sleep(1)

    except Exception as e:
        print(f"Error training person group: {e}")
        return False

def list_persons():
    if not AZURE_FACE_KEY:
        print("Error: AZURE_FACE_KEY not set in .env file")
        return

    try:
        client = FaceAdministrationClient(
            endpoint=AZURE_FACE_ENDPOINT,
            credential=AzureKeyCredential(AZURE_FACE_KEY)
        )

        persons = client.person_group.get_persons(person_group_id=AZURE_FACE_PERSON_GROUP_ID)

        print(f"\nPeople in Person Group '{AZURE_FACE_PERSON_GROUP_ID}':")
        print("-" * 50)

        if not persons:
            print("No people added yet")
        else:
            for person in persons:
                print(f"Name: {person.name}")
                print(f"ID: {person.person_id}")
                print(f"Faces: {len(person.persisted_face_ids)}")
                print("-" * 50)

    except Exception as e:
        print(f"Error listing persons: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Agricultural Intrusion Detection - Face API Setup")
        print("\nUsage:")
        print("  python setup_face_api.py setup          - Create person group")
        print("  python setup_face_api.py add <name> <image.jpg>  - Add person with face image")
        print("  python setup_face_api.py train          - Train person group")
        print("  python setup_face_api.py list           - List all persons")
        print("\nExample:")
        print("  python setup_face_api.py setup")
        print("  python setup_face_api.py add 'John Doe' john.jpg")
        print("  python setup_face_api.py add 'Jane Smith' jane.jpg")
        print("  python setup_face_api.py train")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "setup":
        setup_person_group()
    elif command == "add":
        if len(sys.argv) < 4:
            print("Error: Please provide name and image path")
            print("Usage: python setup_face_api.py add <name> <image.jpg>")
        else:
            name = sys.argv[2]
            image_path = sys.argv[3]
            add_person(name, image_path)
    elif command == "train":
        train_person_group()
    elif command == "list":
        list_persons()
    else:
        print(f"Unknown command: {command}")
        print("Use 'setup', 'add', 'train', or 'list'")
