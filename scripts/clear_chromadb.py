import chromadb
from src.config import settings
from chromadb.config import Settings
import shutil
from pathlib import Path

# Initialize ChromaDB client
persist_dir = Path(settings.chroma_persist_dir)

# Remove the directory completely
if persist_dir.exists():
    print(f"Deleting ChromaDB persistence directory: {persist_dir}")
    shutil.rmtree(persist_dir)
    print("ChromaDB directory deleted.")

# Re-initialize client (this will create the directory again)
client = chromadb.PersistentClient(
    path=str(persist_dir), settings=Settings(anonymized_telemetry=False)
)

# List and delete all collections if any were left
try:
    collections = client.list_collections()
    if collections:
        print(f"Found {len(collections)} existing collections. Deleting...")
        for collection in collections:
            print(f"Deleting collection: {collection.name}")
            client.delete_collection(name=collection.name)
        print("All ChromaDB collections deleted.")
    else:
        print("No existing ChromaDB collections found.")
except Exception as e:
    print(f"Error listing/deleting collections: {e}")

print("ChromaDB has been cleared.")
