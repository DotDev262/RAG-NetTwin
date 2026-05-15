"""
Export ChromaDB chunks to clean all_chunks.json for benchmarking.

Reads from the ChromaDB vector store (populated by cli_chunker.py or
reindex_vector.py) and exports deduplicated, quality-filtered chunks
to data/processed_chunks/all_chunks.json.

Usage:
    uv run python scripts/export_chunks.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.rag.vector_store import VectorStore
from rich.console import Console
from rich.panel import Panel

console = Console()

BOILERPLATE_KEYWORDS = [
    "copyright",
    "all rights reserved",
    "table of contents",
    "preface",
    "intended audience",
    "document history",
    "legal notice",
    "trademark",
    "proprietary information",
]


def main():
    console.print(
        Panel(
            "[bold yellow]ChromaDB → all_chunks.json Export[/bold yellow]",
            expand=False,
            border_style="yellow",
        )
    )

    store = VectorStore()

    console.print("[bold blue]Reading all chunks from ChromaDB...[/bold blue]")
    all_data = store.collection.get()
    if not all_data or not all_data.get("ids"):
        console.print("[bold red]No chunks found in ChromaDB![/bold red]")
        sys.exit(1)

    ids: List[str] = all_data["ids"]
    documents: List[str] = all_data["documents"]
    metadatas: List[Dict[str, Any]] = all_data["metadatas"]

    console.print(f"Read {len(ids)} raw chunks from ChromaDB")

    chunks = []
    for i in range(len(ids)):
        meta = metadatas[i] if metadatas else {}
        text = documents[i] if documents else ""
        tier = meta.get("tier", 2)
        vendor = meta.get("vendor", "unknown")
        os_version = meta.get("os_version", "unknown")

        chunk_id = ids[i]
        source_file = meta.get("source_file", "unknown")

        try:
            page_range = json.loads(meta.get("page_range", "[0, 0]"))
        except (json.JSONDecodeError, TypeError):
            page_range = [0, 0]

        try:
            context_tags = json.loads(meta.get("context_tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            context_tags = []

        try:
            command_hierarchy = json.loads(meta.get("command_hierarchy", "[]"))
        except (json.JSONDecodeError, TypeError):
            command_hierarchy = []

        chunks.append(
            {
                "id": chunk_id,
                "text": text,
                "tier": tier,
                "vendor": vendor,
                "os_version": os_version,
                "source_file": source_file,
                "page_range": page_range,
                "context_tags": context_tags,
                "command_hierarchy": command_hierarchy,
            }
        )

    # Quality gate: filter too-short and boilerplate
    initial_count = len(chunks)
    filtered = []
    for c in chunks:
        text_lower = c["text"].lower()
        tier = c["tier"]
        if tier == 1:
            if len(c["text"]) > 40:
                filtered.append(c)
            continue
        if len(c["text"]) < 150:
            continue
        if any(kw in text_lower for kw in BOILERPLATE_KEYWORDS):
            continue
        filtered.append(c)

    removed = initial_count - len(filtered)
    console.print(
        f"Quality gate: removed {removed} noise chunks, {len(filtered)} remaining"
    )

    # Deduplicate by full text
    seen_texts = {}
    for c in filtered:
        key = c["text"]
        if key not in seen_texts:
            seen_texts[key] = c
    unique = list(seen_texts.values())
    dup_count = len(filtered) - len(unique)
    if dup_count:
        console.print(
            f"Dedup: removed {dup_count} duplicate texts, {len(unique)} remaining"
        )

    # Write to all_chunks.json
    out_dir = Path("data/processed_chunks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "all_chunks.json"

    with open(out_path, "w") as f:
        json.dump(unique, f, indent=2)

    console.print(
        Panel(
            f"[bold green]✓ Exported {len(unique)} chunks to {out_path}[/bold green]\n"
            f"   Removed {removed} noise + {dup_count} duplicates = {initial_count - len(unique)} total waste",
            expand=False,
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
