#!/usr/bin/env python3
"""
Quick script to ingest processed documents into ChromaDB
"""

import sys

sys.path.insert(0, "src")

from src.rag.vector_store import VectorStore
from pathlib import Path
import uuid


def chunk_text(text, chunk_size=512, overlap=50):
    """Simple chunking strategy"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)

    return chunks


def ingest_documents():
    print("🚀 Starting document ingestion...")

    # Initialize vector store
    store = VectorStore()

    # Check current stats
    stats = store.get_stats()
    print(f"📊 Current vector DB stats: {stats}")

    if stats["total_chunks"] > 0:
        print(
            f"✅ Vector DB already has {stats['total_chunks']} chunks. Skipping ingestion."
        )
        return

    # Process extracted files
    processed_dir = Path("data/processed")
    text_files = list(processed_dir.glob("*.txt"))

    print(f"📁 Found {len(text_files)} text files to process")

    total_chunks = 0

    for txt_file in text_files:
        print(f"\n📄 Processing: {txt_file.name}")

        # Read file
        with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # Detect vendor and OS version from filename
        filename = txt_file.stem.lower()

        if "cisco" in filename or "catalyst" in filename or "ios" in filename:
            vendor = "cisco"
            if "17_6" in filename or "17.6" in filename:
                os_version = "ios-xe-17.6"
            else:
                os_version = "ios-xe"
        elif "junos" in filename or "juniper" in filename:
            vendor = "juniper"
            os_version = "junos-21.4"
        else:
            vendor = "cisco"
            os_version = "ios-xe-17.6"

        # Chunk the text
        chunks = chunk_text(text)
        print(f"   ✂️  Created {len(chunks)} chunks")

        # Prepare chunks for vector store
        chunk_objects = []
        for i, chunk_text_content in enumerate(chunks):
            chunk_id = f"{vendor}_{os_version}_{uuid.uuid4().hex[:8]}"

            # Create chunk object
            class Chunk:
                pass

            chunk = Chunk()
            chunk.id = chunk_id
            chunk.text = chunk_text_content[:4000]  # Limit size
            chunk.tier = 1  # Syntax tier
            chunk.vendor = vendor
            chunk.os_version = os_version
            chunk.command_hierarchy = {"section": "general"}
            chunk.context_tags = [vendor, os_version]
            chunk.source_file = str(txt_file)
            chunk.page_range = [0, 0]

            chunk_objects.append(chunk)

        # Add to vector store
        if chunk_objects:
            store.add_chunks(chunk_objects)
            total_chunks += len(chunk_objects)
            print(f"   ✅ Added {len(chunk_objects)} chunks")

    # Final stats
    final_stats = store.get_stats()
    print("\n🎉 Ingestion complete!")
    print(f"📊 Total chunks in database: {final_stats['total_chunks']}")
    print("\n💡 You can now run: uv run python main.py")


if __name__ == "__main__":
    ingest_documents()
