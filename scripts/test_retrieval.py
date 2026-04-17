import sys
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.vector_store import VectorStore

console = Console()

TEST_QUERIES = [
    {"query": "OSPF area configuration", "vendor": "cisco", "version": "ios-xe-17.6"},
    {"query": "BGP neighbor peering", "vendor": "juniper", "version": "junos-21.4"},
    {"query": "Standard Access-list", "vendor": "cisco", "version": "ios-xe-17.6"},
    {"query": "Interface MTU and speed", "vendor": "juniper", "version": "junos-21.4"},
]

def test_hierarchical_retrieval():
    console.print(Panel.fit("[bold cyan]RAG-NetTwin: Balanced Hierarchical Retrieval Test[/bold cyan]\n[dim]Verifying 1 Syntax Chunk (T1) + 1 Context Chunk (T2/3)[/dim]"))
    
    store = VectorStore()
    stats = store.get_stats()
    console.print(f"Index Stats: [green]{stats['total_chunks']} total chunks[/green]\n")

    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        vendor = test["vendor"]
        version = test["version"]
        
        console.print(f"[bold yellow]Test {i}:[/bold yellow] Query: '[italic]{query}[/italic]' | Vendor: [bold]{vendor.upper()}[/bold]")
        
        # --- SIMULATE BALANCED RETRIEVAL LOGIC ---
        results = []
        
        # 1. Fetch Syntax (Tier 1)
        syntax = store.retrieve(query=query, vendor=vendor, os_version=version, tier=1, n_results=1)
        if syntax: results.extend(syntax)
        
        # 2. Fetch Concept (Tier 2/3)
        concept = store.retrieve(query=query, vendor=vendor, os_version=version, tier=2, n_results=1)
        if not concept:
            concept = store.retrieve(query=query, vendor=vendor, os_version=version, tier=3, n_results=1)
        if concept: results.extend(concept)
        
        if not results:
            console.print("  [red]❌ No results found.[/red]\n")
            continue
            
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Tier", justify="center")
        table.add_column("Type")
        table.add_column("Chunk ID")
        table.add_column("Content Snippet", ratio=1)
        
        for res in results:
            tier = str(res['metadata'].get('tier', '?'))
            cmd_type = res['metadata'].get('command_type', 'unknown')
            chunk_id = res['id']
            text = res['text'].replace("\n", " ")[:120] + "..."
            
            # Color code by tier
            tier_display = f"[bold green]{tier}[/bold green]" if tier == "1" else f"[cyan]{tier}[/cyan]"
            
            table.add_row(tier_display, cmd_type, chunk_id, text)
            
        console.print(table)
        console.print("-" * 80 + "\n")

if __name__ == "__main__":
    test_hierarchical_retrieval()
