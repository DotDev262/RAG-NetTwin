import os
import shutil
import sys
import json
from rich.console import Console
from rich.panel import Panel

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.vector_store import VectorStore

console = Console()


def main():
    console.print(
        Panel(
            "[bold yellow]RAG-NetTwin Vector Re-index[/bold yellow]\n"
            "Upgrading to IBM Granite-311M Semantic Space (32k Context)",
            expand=False,
            border_style="yellow",
        )
    )

    # 1. Clear existing Vector DB
    db_path = "./data/chroma_db"
    if os.path.exists(db_path):
        console.print(f"[dim]Clearing existing Vector DB at {db_path}...[/dim]")
        # Close any potential open handles or just remove the dir
        try:
            shutil.rmtree(db_path)
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not fully clear {db_path}: {e}[/yellow]"
            )

    # 2. Re-index Vector DB (Pure Python)
    console.print("\n[bold blue]>>> Initializing VectorStore...[/bold blue]")
    try:
        # VectorStore now handles manual embedding generation for Granite-311M
        store = VectorStore()

        chunks_file = "data/processed_chunks/all_chunks.json"
        if not os.path.exists(chunks_file):
            console.print(f"[red]Error: {chunks_file} not found![/red]")
            sys.exit(1)

        with open(chunks_file, "r") as f:
            chunks = json.load(f)

        # 3. Quality Gate: Filter out noise and boilerplate
        console.print(
            "[bold cyan]>>> Applying Quality Gate (Signal-to-Noise Filtering)...[/bold cyan]"
        )
        initial_count = len(chunks)

        filtered_chunks = []
        boilerplate_keywords = [
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

        for chunk in chunks:
            text = chunk.get("text", "").lower()
            tier = chunk.get("tier", 1)

            # Tier 1 (Authoritative) is high value; keep even if relatively short
            if tier == 1:
                if len(text) > 40:
                    filtered_chunks.append(chunk)
                continue

            # Tier 2/3 filtering
            # 1. Length check
            if len(text) < 150:
                continue

            # 2. Boilerplate check
            if any(kw in text for kw in boilerplate_keywords):
                # Extra check: if it contains a CLI-like character, maybe keep it?
                # For now, stick to conservative filtering
                continue

            filtered_chunks.append(chunk)

        removed_count = initial_count - len(filtered_chunks)
        console.print(
            f"[green]✓ Quality Gate applied: Kept {len(filtered_chunks)} high-signal chunks (Removed {removed_count} noise chunks).[/green]"
        )

        # Deduplicate by full text content
        seen_texts = {}
        for chunk in filtered_chunks:
            text_key = chunk.get("text", "")
            if text_key not in seen_texts:
                seen_texts[text_key] = chunk
        deduped_chunks = list(seen_texts.values())
        dup_count = len(filtered_chunks) - len(deduped_chunks)
        if dup_count:
            console.print(
                f"[yellow]✓ Dedup: removed {dup_count} duplicate texts.[/yellow]"
            )

        console.print(
            f"[bold cyan]>>> Synchronizing {len(deduped_chunks)} chunks with Granite-311M manifold...[/bold cyan]"
        )
        store.add_chunks(deduped_chunks)
        console.print(
            f"\n[bold green]✓ Indexed {len(deduped_chunks)} chunks successfully.[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]✗ Vector indexing failed: {e}[/bold red]")
        sys.exit(1)

    console.print(
        Panel(
            "[bold green]VECTOR RE-INDEX COMPLETE[/bold green]\n"
            "ChromaDB is now synchronized with IBM Granite-311M (Matryoshka-Ready).",
            expand=False,
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
