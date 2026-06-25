import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from tqdm import tqdm  # type: ignore

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
            "[bold cyan]RAG-NetTwin: RAG vs Advanced vs GraphRAG Benchmark[/bold cyan]\n"
            "[dim]Measuring improvements from Knowledge Graph Expansion & Multi-Pass Retrieval[/dim]"
        )
    )

    store = VectorStore()
    from src.rag.query_expander import QueryExpander
    from src.rag.config_generator import ConfigGenerator

    expander = QueryExpander()
    # We use a dummy generator just for the distill_context logic
    generator = ConfigGenerator()

    results = []

    for item in tqdm(BENCHMARK_QUERIES, desc="Benchmarking Retrieval"):
        query = item["q"]
        vendor = item["vendor"]

        # --- MODE 1: BASELINE (Single Query, Standard Retrieval) ---
        baseline_raw = store.hybrid_retrieve(query=query, vendor=vendor, n_results=5)
        # Force baseline rerank (no boost simulation)
        baseline_reranked = store.rerank(query, baseline_raw, n_results=5)
        avg_baseline_score = np.mean(
            [r.get("rerank_score", 0.0) for r in baseline_reranked]
        )
        baseline_context = generator.distill_context(baseline_reranked)

        # --- MODE 2: ADVANCED (Multi-Query + Syntax Reranking) ---
        queries = expander.expand(query)
        all_adv_candidates = []
        for q in queries:
            all_adv_candidates.extend(
                store.hybrid_retrieve(query=q, vendor=vendor, n_results=5)
            )

        unique_adv = list({c["id"]: c for c in all_adv_candidates}.values())
        adv_reranked = store.rerank(query, unique_adv, n_results=5)
        avg_adv_score = np.mean([r.get("rerank_score", 0.0) for r in adv_reranked])
        adv_context = generator.distill_context(adv_reranked)

        # --- MODE 3: GRAPHRAG (Syntax Seeds + Community Cluster Expansion) ---
        all_graph_candidates = []
        for q in queries:
            # 1. Start with Syntax Seeds
            seeds = store.hybrid_retrieve(query=q, vendor=vendor, tier=1, n_results=3)
            # 2. Expand using Knowledge Graph Communities (SOTA)
            expanded = store.retrieve_community_context(seeds)
            all_graph_candidates.extend(expanded)

        unique_graph = list({c["id"]: c for c in all_graph_candidates}.values())
        graph_reranked = store.rerank(query, unique_graph, n_results=5)
        avg_graph_score = np.mean([r.get("rerank_score", 0.0) for r in graph_reranked])
        graph_context = generator.distill_context(graph_reranked)

        results.append(
            {
                "query": query,
                "baseline": avg_baseline_score,
                "advanced": avg_adv_score,
                "graphrag": avg_graph_score,
                "baseline_len": len(baseline_context),
                "adv_len": len(adv_context),
                "graph_len": len(graph_context),
                "improvement": (
                    (avg_graph_score - avg_baseline_score) / avg_baseline_score * 100
                )
                if avg_baseline_score != 0
                else 0,
            }
        )

    # Display Table
    table = Table(
        title="3-Way Retrieval Comparison",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Query", ratio=1)
    table.add_column("Baseline", justify="right")
    table.add_column("Advanced", justify="right")
    table.add_column("GraphRAG", justify="right", style="bold green")
    table.add_column("Gain (%)", justify="right")

    for r in results:
        table.add_row(
            r["query"][:40] + "...",
            f"{r['baseline']:.3f}",
            f"{r['advanced']:.3f}",
            f"{r['graphrag']:.3f}",
            f"{r['improvement']:.1f}%",
        )

    console.print(table)

    # Final Stats
    summary = f"""
    [bold underline]Performance Summary[/bold underline]
    
    [bold]Avg Semantic Precision (Baseline):[/bold]  {np.mean([r["baseline"] for r in results]):.4f}
    [bold]Avg Semantic Precision (GraphRAG):[/bold] [green]{np.mean([r["graphrag"] for r in results]):.4f}[/green]
    
    [bold]Avg Context Efficiency:[/bold]
    - Baseline Context Size:  {np.mean([r["baseline_len"] for r in results]):.0f} chars
    - GraphRAG Context Size:  {np.mean([r["graph_len"] for r in results]):.0f} chars
    
    [bold blue]Conclusion:[/bold blue] GraphRAG provides [bold green]{np.mean([r["improvement"]]):.2f}%[/bold green] better context reach than baseline.
    """
    console.print(Panel(summary, border_style="green"))

    console.print(table)

    # Summary Panel
    avg_gain = np.mean([r["improvement"] for r in results])

    summary = f"""
    [bold]Mean Semantic Precision (Baseline):[/bold] [white]{np.mean([r["baseline"] for r in results]):.4f}[/white]
    [bold]Mean Semantic Precision (GraphRAG):[/bold] [green]{np.mean([r["graphrag"] for r in results]):.4f}[/green]

    [bold]Avg Context Chars (Baseline):[/bold]       [cyan]{np.mean([r["baseline_len"] for r in results]):.0f}[/cyan]
    [bold]Avg Context Chars (GraphRAG):[/bold]     [cyan]{np.mean([r["graph_len"] for r in results]):.0f}[/cyan]
    [bold]Average Retrieval Improvement:[/bold]     [bold green]{avg_gain:.2f}%[/bold green]

    [dim]Note: Scores are calculated using the local Alibaba-NLP/gte-reranker-modernbert-base Cross-Encoder.[/dim]
    """

    console.print(Panel(summary, title="Benchmark Summary", border_style="bold green"))


if __name__ == "__main__":
    run_graph_benchmark()
