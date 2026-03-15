"""
Hybrid Chunker: Combines CLI examples with original documentation
Uses regex to find CLI-like content in existing chunks and boosts those.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_processing.pdf_extractor import extract_text_from_pdf
from data_processing.chunker import HierarchicalChunker
from rag.vector_store import VectorStore


def is_cli_like(text: str) -> bool:
    """Check if text looks like CLI commands."""
    cli_indicators = [
        r"^interface\s+",
        r"^router\s+",
        r"^ip\s+(address|route|access-list)",
        r"^vlan\s+",
        r"^switchport",
        r"^hostname",
        r"^\s+(network|neighbor|area)",
        r"^set\s+",
    ]
    lines = text.split("\n")
    cli_lines = sum(
        1
        for line in lines
        if any(re.match(p, line.strip(), re.I) for p in cli_indicators)
    )
    return cli_lines >= 2


def process_and_hybrid_index():
    """Process docs with CLI priority and original content as fallback."""
    vector_store = VectorStore()

    # Clear existing
    print("Clearing existing collection...")
    try:
        existing = vector_store.collection.get()
        if existing.get("ids"):
            vector_store.collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"  Note: {e}")

    all_chunks = []

    # Process each doc with both chunkers
    docs = [
        ("data/raw_docs/catalyst_9300_cmdref_17_6.pdf", "cisco", "ios-xe-17.6"),
        ("data/raw_docs/catalyst_9500_cmdref_17_6.pdf", "cisco", "ios-xe-17.6"),
        ("data/raw_docs/junos-cli.pdf", "juniper", "junos-21.4"),
        ("data/raw_docs/junos-ospf.pdf", "juniper", "junos-21.4"),
    ]

    for pdf_path, vendor, os_version in docs:
        if not Path(pdf_path).exists():
            continue

        print(f"Processing {Path(pdf_path).name}...")

        # Extract pages
        pages = extract_text_from_pdf(pdf_path)

        # Use hierarchical chunker with unique prefix
        prefix = Path(pdf_path).stem[:4]  # e.g., cata, juno
        chunker = HierarchicalChunker(vendor, os_version)
        chunker.chunk_id_counter = len(all_chunks)  # Continue from previous
        chunks = chunker.chunk_document(pages)

        # Mark CLI-like chunks with higher tier (1 = highest priority)
        for chunk in chunks:
            if is_cli_like(chunk.text):
                chunk.tier = 1  # Boost CLI-like content
            chunk_dict = {
                "id": chunk.id,
                "text": chunk.text,
                "vendor": chunk.vendor,
                "os_version": chunk.os_version,
                "tier": chunk.tier,
                "command_hierarchy": chunk.command_hierarchy,
                "context_tags": chunk.context_tags,
            }
            all_chunks.append(chunk_dict)

        print(f"  Created {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")

    # Add to vector store
    texts = [c["text"] for c in all_chunks]
    metadatas = [
        {
            "vendor": c["vendor"],
            "os_version": c["os_version"],
            "tier": c["tier"],
            "source": "hybrid_chunker",
        }
        for c in all_chunks
    ]
    ids = [c["id"] for c in all_chunks]

    vector_store.collection.add(ids=ids, documents=texts, metadatas=metadatas)
    print(f"Added {len(all_chunks)} chunks to vector store")

    # Stats
    tier_counts = {}
    vendor_counts = {}
    for c in all_chunks:
        tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1
        vendor_counts[c["vendor"]] = vendor_counts.get(c["vendor"], 0) + 1

    print(f"\nTier distribution: {tier_counts}")
    print(f"Vendor distribution: {vendor_counts}")


if __name__ == "__main__":
    process_and_hybrid_index()
