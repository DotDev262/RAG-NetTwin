import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from tqdm import tqdm

from src.rag.vector_store import VectorStore

console = Console()

# 10 Diverse Research Queries for Benchmarking
BENCHMARK_QUERIES = [
    {"q": "Configure OSPF area 0 on GigabitEthernet interface", "vendor": "cisco"},
    {"q": "Set up BGP neighbor with remote autonomous system", "vendor": "juniper"},
    {"q": "Create extended access-list to block TCP port 80", "vendor": "cisco"},
    {"q": "Enable IPv6 routing and assign global address", "vendor": "cisco"},
    {"q": "Configure VLAN tagging on trunk port", "vendor": "juniper"},
    {"q": "Set up static route to destination network via next-hop", "vendor": "cisco"},
    {"q": "Enable SNMP community with read-only access", "vendor": "juniper"},
    {"q": "Configure NTP server for time synchronization", "vendor": "cisco"},
    {"q": "Set system hostname and domain name", "vendor": "juniper"},
    {"q": "Configure local user with privilege level and secret", "vendor": "cisco"},
]


def run_graph_benchmark():
    console.print(
        Panel.fit(
            "[bold cyan]RAG-NetTwin: Advanced RAG vs Baseline Retrieval Benchmark[/bold cyan]\n"
            "[dim]Measuring improvements from Multi-Query Expansion & Syntax-Aware Reranking[/dim]"
        )
    )

    store = VectorStore()
    # We'll use the query expander already integrated in ConfigGenerator logic
    from src.rag.query_expander import QueryExpander

    expander = QueryExpander()

    results = []

    for item in tqdm(BENCHMARK_QUERIES, desc="Benchmarking Retrieval"):
        query = item["q"]
        vendor = item["vendor"]

        # --- MODE 1: BASELINE (Single Query, Flat Hybrid) ---
        # start_t = time.time()
        # Just use the original query, standard retrieval
        baseline_candidates = store.hybrid_retrieve(
            query=query, vendor=vendor, n_results=10
        )

        # Standard Rerank (using a mock without syntax boost for baseline)
        # We simulate the old rerank by disabling the boost logic or just taking top chunks
        baseline_results = sorted(
            baseline_candidates, key=lambda x: x.get("distance", 1.0)
        )[:5]

        # Calculate Average Relevance (Cross-Encoder score on baseline)
        baseline_reranked = store.rerank(query, baseline_results, n_results=5)
        avg_baseline_score = np.mean(
            [r.get("rerank_score", 0.0) for r in baseline_reranked]
        )

        # --- MODE 2: ADVANCED (Multi-Query + Syntax-Aware Reranking) ---
        # 1. Expand Queries
        queries = expander.expand(query)

        # 2. Accumulate Candidates
        all_candidates = []
        for q in queries:
            # Hierarchical Retrieval (Tiered)
            s_cand = store.hybrid_retrieve(query=q, vendor=vendor, tier=1, n_results=3)
            c_cand = store.hybrid_retrieve(query=q, vendor=vendor, tier=2, n_results=3)
            all_candidates.extend(s_cand + c_cand)

        # Deduplicate
        unique_candidates = {c["id"]: c for c in all_candidates}.values()

        # 3. Syntax-Aware Reranking (Already implemented in VectorStore.rerank)
        advanced_results = store.rerank(query, list(unique_candidates), n_results=5)
        avg_advanced_score = np.mean(
            [r.get("rerank_score", 0.0) for r in advanced_results]
        )

        # Information Gain: Total unique chunks considered
        total_unique = len(unique_candidates)

        results.append(
            {
                "query": query,
                "vendor": vendor,
                "baseline_score": avg_baseline_score,
                "advanced_score": avg_advanced_score,
                "candidates_found": total_unique,
                "improvement": (
                    (avg_advanced_score - avg_baseline_score) / avg_baseline_score * 100
                )
                if avg_baseline_score != 0
                else 0,
            }
        )

    # Display Table
    table = Table(
        title="RAG Performance: Advanced vs Baseline",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Query Preview", ratio=1)
    table.add_column("Baseline Score", justify="right")
    table.add_column("Advanced Score", justify="right")
    table.add_column("Recall (Unique Chunks)", justify="center")
    table.add_column("Gain (%)", justify="right")

    for r in results:
        color = (
            "green"
            if r["improvement"] > 0
            else ("red" if r["improvement"] < 0 else "white")
        )
        table.add_row(
            r["query"][:40] + "...",
            f"{r['baseline_score']:.4f}",
            f"{r['advanced_score']:.4f}",
            str(r["candidates_found"]),
            f"[{color}]{r['improvement']:.1f}%[/{color}]",
        )

    console.print(table)

    # Summary Panel
    avg_gain = np.mean([r["improvement"] for r in results])
    total_candidates = sum([r["candidates_found"] for r in results])

    summary = f"""
    [bold]Mean Semantic Precision (Baseline):[/bold] [white]{np.mean([r['baseline_score'] for r in results]):.4f}[/white]
    [bold]Mean Semantic Precision (Advanced):[/bold] [green]{np.mean([r['advanced_score'] for r in results]):.4f}[/green]

    [bold]Total Candidates Considered:[/bold]       [cyan]{total_candidates}[/cyan]
    [bold]Average Retrieval Improvement:[/bold]     [bold green]{avg_gain:.2f}%[/bold green]

    [dim]Note: Scores are calculated using the local BAAI/bge-reranker-v2-m3 Cross-Encoder.[/dim]
    """

    console.print(Panel(summary, title="Benchmark Summary", border_style="bold green"))


if __name__ == "__main__":
    run_graph_benchmark()
