"""
Grounding Audit Demo Script for RAG-NetTwin.

This script provides an interactive command-line interface for demonstrating
the "Grounding Audit Trail" feature. Users can look up specific chunk IDs
to see the source documentation that was used to generate a network configuration.

This is a key feature for:
- Verifying configurations came from real vendor documentation
- Debugging incorrect configurations
- Building trust in the RAG-NetTwin system
- Demonstrating the "grounding" aspect of RAG

Key Features:
- Interactive lookup of chunk IDs from the knowledge base
- Syntax highlighting for CLI content
- Rich terminal UI with formatted tables and panels

Typical Usage:
    # Interactive mode - prompts for chunk IDs
    python scripts/audit_demo.py

    # Direct lookup - specify chunk ID as argument
    python scripts/audit_demo.py chunk_000362

Note:
    This script requires the processed chunks file at:
    data/processed_chunks/all_chunks.json
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import json
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CHUNKS_FILE = PROJECT_ROOT / "data" / "processed_chunks" / "all_chunks.json"

# Initialize Rich console for formatted output
console = Console()


def load_index():
    """
    Load the processed chunks index from JSON file.

    This function reads the all_chunks.json file which contains all
    processed documentation chunks from vendor PDFs. It creates an
    in-memory dictionary for O(1) lookup by chunk ID.

    Returns:
        Dictionary mapping chunk IDs to their full chunk data.

    Raises:
        SystemExit: If chunks file doesn't exist or fails to load.
    """
    if not CHUNKS_FILE.exists():
        console.print(f"[red]Error:[/red] Could not find {CHUNKS_FILE}")
        sys.exit(1)

    # Only show status in interactive mode or if verbose
    with console.status(
        "[bold blue]Loading Grounding Knowledge Base...", spinner="dots"
    ):
        try:
            with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Create a lookup dictionary for O(1) access
            # This allows instant retrieval by chunk ID
            index = {chunk["id"]: chunk for chunk in data}
            return index
        except Exception as e:
            console.print(f"[red]Failed to load index:[/red] {e}")
            sys.exit(1)


def display_chunk(chunk_id: str, index: dict) -> bool:
    """
    Display a single chunk's metadata and content.

    This function retrieves a chunk by ID and displays it with rich
    formatting. It shows:
    - Metadata table (vendor, OS version, source file)
    - Content panel with syntax highlighting for CLI

    Args:
        chunk_id: The unique identifier of the chunk to display.
        index: Dictionary mapping chunk IDs to chunk data.

    Returns:
        True if chunk was found and displayed, False otherwise.
    """
    chunk = index.get(chunk_id)

    if not chunk:
        console.print(f"[red]No record found for ID: {chunk_id}[/red]\n")
        return False

    # Extract metadata if available
    vendor = chunk.get("vendor", "Unknown")
    os_ver = chunk.get("os_version", "Unknown")
    source = chunk.get("source_file", "Unknown")
    page_range = chunk.get("page_range", [])
    tier = chunk.get("tier", "Unknown")

    # Header Table - displays chunk metadata
    table = Table(show_header=False, box=None)
    table.add_row("[bold]Chunk ID:[/bold]", f"[cyan]{chunk_id}[/cyan]")
    table.add_row("[bold]Vendor:[/bold]", f"[magenta]{vendor.upper()}[/magenta]")
    table.add_row("[bold]OS/Version:[/bold]", f"[yellow]{os_ver}[/yellow]")
    table.add_row("[bold]Source File:[/bold]", f"[dim]{source}[/dim]")
    pages = f"{page_range[0]}-{page_range[1]}" if len(page_range) >= 2 else str(page_range[0]) if page_range else "N/A"
    table.add_row("[bold]Pages:[/bold]", f"[yellow]{pages}[/yellow]")
    table.add_row("[bold]Tier:[/bold]", f"[yellow]{tier}[/yellow]")

    console.print(Panel(table, title="Metadata", border_style="blue"))

    # Content Panel - displays the actual documentation text
    content = chunk.get("text", "").strip()
    # If it looks like CLI code, apply syntax highlighting
    # Cisco uses "!" for comments, Juniper uses "set" commands
    if "!" in content[:20] or "set " in content[:20]:
        view = Syntax(content, "bash", theme="monokai", line_numbers=True)
    else:
        view = content

    console.print(
        Panel(
            view,
            title=f"Source Documentation - {chunk_id}",
            subtitle="Authoritative Vendor Knowledge",
            border_style="green",
            padding=(1, 2),
        )
    )
    return True


def main():
    """
    Main entry point for the Grounding Audit Demo.

    Provides an interactive prompt where users can enter chunk IDs
    to view the source documentation that was used to generate
    network configurations.

    Supports two modes:
    1. Interactive mode: Prompts for chunk IDs in a loop
    2. Direct mode: Accepts chunk ID as command-line argument
    """
    parser = argparse.ArgumentParser(description="RAG-NetTwin Grounding Audit Demo")
    parser.add_argument("chunk_ids", nargs="*", help="Chunk ID(s) to lookup")
    args = parser.parse_args()

    # Direct mode: lookup one or more chunks and exit
    if args.chunk_ids:
        index = load_index()
        for cid in args.chunk_ids:
            display_chunk(cid, index)
        return

    # Interactive mode: show welcome message and start prompt loop
    console.print(
        Panel.fit(
            "[bold cyan]RAG-NetTwin Grounding Audit Demo[/bold cyan]\n"
            "[dim]Enter a Chunk ID (e.g., chunk_000362) to see its source documentation.[/dim]",
            border_style="cyan",
        )
    )

    index = load_index()
    console.print(
        f"[green]Successfully indexed {len(index)} document chunks.[/green]\n"
    )

    # Main interactive loop
    while True:
        try:
            # Prompt for chunk ID
            chunk_id = console.input(
                "[bold yellow]Audit Trail ID > [/bold yellow]"
            ).strip()

            if not chunk_id:
                continue

            # Check for exit commands
            if chunk_id.lower() in ["exit", "quit", "q"]:
                break

            # Display the requested chunk
            display_chunk(chunk_id, index)
            console.print("\n")

        except KeyboardInterrupt:
            break

    console.print("\n[bold blue]Exiting Grounding Audit Demo.[/bold blue]")


if __name__ == "__main__":
    main()
