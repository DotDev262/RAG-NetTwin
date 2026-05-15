import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.rag.vector_store import VectorStore
from src.config import settings

console = Console()


def test_retrieval(query: str, vendor: str = "cisco"):
    console.print(
        Panel(
            f"[bold yellow]RAG Dry-Run (No LLM Call)[/bold yellow]\n"
            f"Query: [cyan]{query}[/cyan]\n"
            f"Vendor: [magenta]{vendor}[/magenta]\n"
            f"Stack: {settings.embedding_model_name} + {settings.reranker_model_name}",
            expand=False,
        )
    )

    # 1. Initialize Vector Store
    console.print("[dim]Initializing VectorStore...[/dim]")
    try:
        store = VectorStore()
    except Exception as e:
        console.print(f"[bold red]Initialization failed: {e}[/bold red]")
        return

    # 2. Perform Retrieval
    console.print(f"[dim]Retrieving documentation for: '{query}'...[/dim]")

    # 1. Hybrid Search (Semantic + BM25)
    candidates = store.hybrid_retrieve(query=query, vendor=vendor, n_results=10)

    # 2. Cross-Encoder Reranking
    results = store.rerank(query=query, chunks=candidates, n_results=5)

    # 3. Parent Document Enhancement
    final_results = store.retrieve_with_parents(results)

    # 3. Display Results
    table = Table(title="Retrieved Documentation Chunks (Reranked & Enhanced)")
    table.add_column("Rank", justify="center", style="dim")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Source", style="blue")
    table.add_column("Content Snippet", style="white")

    for i, doc in enumerate(final_results):
        snippet = doc["text"][:150].replace("\n", " ") + "..."
        # Use rerank_score if available
        score = (
            f"{doc.get('rerank_score', 'N/A'):.4f}"
            if isinstance(doc.get("rerank_score"), float)
            else "N/A"
        )
        table.add_row(
            str(i + 1),
            score,
            doc.get("metadata", {}).get("source_file", "Unknown"),
            snippet,
        )

    console.print(table)

    # 4. Check Knowledge Graph Context
    if store.graph:
        console.print("\n[bold cyan]Network Concept Graph Context:[/bold cyan]")
        # Find related communities or entities
        # (This uses the logic from src/rag/vector_store.py:retrieve_community_context)
        try:
            # Check for direct entity matches in query
            related_nodes = [
                n
                for n, d in store.graph.nodes(data=True)
                if d.get("label", "").lower() in query.lower()
            ]
            if related_nodes:
                console.print(
                    f"Entities matched in graph: [yellow]{', '.join(related_nodes)}[/yellow]"
                )

                # Fetch community info
                for node in related_nodes[:3]:
                    neighbors = list(store.graph.neighbors(node))
                    console.print(
                        f"→ Node [bold]{node}[/bold] connects to: [dim]{', '.join(neighbors[:5])}...[/dim]"
                    )
            else:
                console.print(
                    "[dim]No direct graph entity matches found in query.[/dim]"
                )
        except Exception as e:
            console.print(f"[dim]Graph analysis skipped: {e}[/dim]")


if __name__ == "__main__":
    # Test queries
    test_queries = [
        {"q": "Configure OSPF area 0 on Catalyst 9300", "v": "cisco"},
        {"q": "Enable BFD for BGP neighbors", "v": "cisco"},
        {"q": "Set up VLAN 10 tagging", "v": "juniper"},
    ]

    # Use first query by default or take from sys.argv
    q = sys.argv[1] if len(sys.argv) > 1 else test_queries[0]["q"]
    v = sys.argv[2] if len(sys.argv) > 2 else "cisco"

    test_retrieval(q, v)
