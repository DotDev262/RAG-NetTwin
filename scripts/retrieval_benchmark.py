import sys
from pathlib import Path
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.vector_store import VectorStore
from utils import calculate_mrr, calculate_ndcg

console = Console()

# Example Benchmark: Mapping Query -> Expected Chunk ID
# In your actual research, you would manually verify these 10-20 IDs
RETRIEVAL_BENCHMARK = [
    {
        "query": "OSPF network area configuration",
        "vendor": "cisco",
        "expected_id": "cisco_tier2_cfafeaa86d27" 
    },
    {
        "query": "BGP neighbor autonomous-system",
        "vendor": "juniper",
        "expected_id": "juniper_tier2_fb57e9215df3"
    },
    {
        "query": "standard access-list permit deny",
        "vendor": "cisco",
        "expected_id": "cisco_tier2_57383a2965b1"
    }
]

def run_benchmark():
    console.print(Panel.fit("[bold cyan]RAG-NetTwin: IR Retrieval Benchmark[/bold cyan]\n[dim]Calculating MRR & NDCG for Elite Retrieval Engine[/dim]"))
    
    store = VectorStore()
    mrr_scores = []
    ndcg_scores = []

    table = Table(title="Retrieval Metrics per Query", show_header=True, header_style="bold magenta")
    table.add_column("Query", ratio=1)
    table.add_column("Found at Rank", justify="center")
    table.add_column("MRR", justify="right")
    table.add_column("NDCG", justify="right")

    for test in RETRIEVAL_BENCHMARK:
        query = test["query"]
        vendor = test["vendor"]
        expected = test["expected_id"]

        # Simulate the full pipeline: Hybrid Recall + Reranking
        # Note: We retrieve 10 to see where the truth falls in the ranks
        candidates = store.hybrid_retrieve(query=query, vendor=vendor, n_results=10)
        
        # Rerank them
        ranked_results = store.rerank(query, candidates, n_results=10)
        retrieved_ids = [res["id"] for res in ranked_results]
        
        # Debugging: Show what was actually found
        console.print(f"    [dim]Retrieved: {retrieved_ids[:3]}[/dim]")

        # Calculate metrics
        mrr = calculate_mrr(expected, retrieved_ids)
        ndcg = calculate_ndcg(expected, retrieved_ids)
        
        mrr_scores.append(mrr)
        ndcg_scores.append(ndcg)

        rank = retrieved_ids.index(expected) + 1 if expected in retrieved_ids else "N/A"
        table.add_row(query, str(rank), f"{mrr:.4f}", f"{ndcg:.4f}")

    console.print(table)

    # Summary Panel
    summary = f"""
    [bold]Mean Reciprocal Rank (MRR):[/bold]  [green]{np.mean(mrr_scores):.4f}[/green]
    [bold]Average NDCG:[/bold]               [green]{np.mean(ndcg_scores):.4f}[/green]
    
    [dim]Perfect retrieval = 1.0000[/dim]
    """
    console.print(Panel(summary, title="Aggregate IR Results", border_style="green"))

if __name__ == "__main__":
    run_benchmark()
