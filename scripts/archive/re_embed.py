#!/usr/bin/env python3
import sys

sys.path.insert(0, "src")
import warnings

warnings.filterwarnings("ignore")

import json  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402
from src.config import settings  # noqa: E402
import os  # noqa: E402

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_WEB"] = "1"

COLLECTION_NAME = "network_docs"
MODEL_PATH = "./models/e5-small-v2"

print(f"Loading model from {MODEL_PATH}...", flush=True)
model = SentenceTransformer(MODEL_PATH)

with open("data/processed_chunks/all_chunks.json", "r") as f:
    chunks = json.load(f)

print(f"Total chunks: {len(chunks)}", flush=True)

client = chromadb.PersistentClient(
    path=str(settings.chroma_persist_dir), settings=Settings(anonymized_telemetry=False)
)

# Delete and recreate collection
try:
    client.delete_collection(COLLECTION_NAME)
    print("Deleted old collection", flush=True)
except Exception:
    pass

collection = client.create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
    embedding_function=None,  # We'll provide embeddings explicitly
)
print("Created new collection", flush=True)

# Process in batches
batch_size = 50
for i in range(0, len(chunks), batch_size):
    batch = chunks[i : i + batch_size]

    # Generate embeddings locally
    texts = [c["text"] for c in batch]
    embeddings = model.encode(texts, normalize_embeddings=True)

    # Prepare data
    ids = [c["id"] for c in batch]
    metadatas = [
        {
            "vendor": c["vendor"],
            "os_version": c.get("os_version", c.get("os", "unknown")),
            "protocol": c.get("protocol", "general"),
            "source": c.get("source", c.get("source_file", "unknown")),
        }
        for c in batch
    ]

    # Add to collection with explicit embeddings
    collection.add(
        ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings.tolist()
    )

    if (i + batch_size) % 500 == 0 or i + batch_size >= len(chunks):
        print(f"Progress: {min(i + batch_size, len(chunks))}/{len(chunks)}", flush=True)

print(f"Done! Final count: {collection.count()}", flush=True)

# Quick test
test_results = collection.query(query_texts=["OSPF configuration"], n_results=2)
print(
    f"Test query results: {len(test_results['ids'][0]) if test_results['ids'] else 0}"
)
