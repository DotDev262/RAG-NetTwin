import json
import time
import sys
import numpy as np
import shutil
import glob
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from rich.console import Console
from rich.table import Table
import chromadb
from chromadb.config import Settings

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).parent.parent))


console = Console()

# Device detection for GPU acceleration
if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"

console.print(f"[dim]Using device: {DEVICE}[/dim]")


def global_cleanup():
    """Wipe any lingering temporary chroma directories."""
    tmp_dirs = glob.glob("./data/tmp_chroma_*")
    if tmp_dirs:
        console.print(
            f"[dim]Cleaning up {len(tmp_dirs)} lingering temp directories...[/dim]"
        )
        for d in tmp_dirs:
            try:
                shutil.rmtree(d)
            except Exception:
                pass


RETRIEVAL_BENCHMARK = [
    # Original baseline
    {
        "query": "LISP site registration information show command",
        "vendor": "cisco",
        "expected_id": "chunk_000050",
    },
    {
        "query": "display LISP IPv4 address-family packet count statistics",
        "vendor": "cisco",
        "expected_id": "chunk_000051",
    },
    {
        "query": "show lisp prefix-list information",
        "vendor": "cisco",
        "expected_id": "chunk_000052",
    },
    # Edge Case 1: Specific Parameter Values (Difficulty: Medium)
    {
        "query": "how to set the LISP map-cache limit to 5000 entries",
        "vendor": "cisco",
        "expected_id": "chunk_000053",
    },
    # Edge Case 2: Multi-vendor Confusion (Junos query in a pool of mixed docs)
    {
        "query": "show ospf database external detail command on junos",
        "vendor": "juniper",
        "expected_id": "chunk_000105",
    },
    # Edge Case 3: Abstract Architectural Concepts
    {
        "query": "difference between LISP proxy-itrs and proxy-etrs implementation",
        "vendor": "cisco",
        "expected_id": "chunk_000054",
    },
    # Edge Case 4: Troubleshooting / Error states
    {
        "query": "troubleshoot lisp registration failures and timeout events",
        "vendor": "cisco",
        "expected_id": "chunk_000055",
    },
    # Edge Case 5: Complex Routing Policy (Junos)
    {
        "query": "define a routing policy term with community and local-preference",
        "vendor": "juniper",
        "expected_id": "chunk_000110",
    },
    # Edge Case 6: Hardware Specifics
    {
        "query": "catalyst 9300 stackwise-virtual configuration requirements",
        "vendor": "cisco",
        "expected_id": "chunk_000200",
    },
    # Edge Case 7: Syntax Similarity (Matching a specific flag)
    {
        "query": "show lisp site detail vs show lisp site summary",
        "vendor": "cisco",
        "expected_id": "chunk_000056",
    },
]


def prepare_candidates(embed_model_name, chunks_path):
    """
    invariant preparation: Load embedder, index chunks, and run initial retrieval.
    Returns a list of candidate sets for reranking.
    """
    console.print(
        "\n[bold green]>>> Preparing Initial Retrieval Candidates...[/bold green]"
    )

    # 1. Load Embedder
    console.print(f"[dim]Loading embedder: {embed_model_name} on {DEVICE}...[/dim]")
    try:
        embed_model = SentenceTransformer(
            embed_model_name,
            device=DEVICE,
            trust_remote_code=True,
            model_kwargs={"default_task": "retrieval"}
            if "jina" in embed_model_name.lower()
            else {},
        )
    except Exception as e:
        console.print(f"[red]Failed to load embedder: {e}[/red]")
        return None

    # 2. Index Chunks
    console.print("[dim]Loading and encoding chunks...[/dim]")
    client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    collection = client.create_collection(
        name="rerank_candidates", metadata={"hnsw:space": "cosine"}
    )

    with open(chunks_path, "r") as f:
        all_chunks = json.load(f)

    expected_ids = {test["expected_id"] for test in RETRIEVAL_BENCHMARK}
    relevant_chunks = [c for c in all_chunks if c["id"] in expected_ids]
    # Increase noise significantly to make retrieval more challenging
    noise_chunks = [c for c in all_chunks if c["id"] not in expected_ids][:500]
    chunks = relevant_chunks + noise_chunks

    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [{"vendor": c["vendor"]} for c in chunks]

    encode_kwargs = {"task": "retrieval"} if "jina" in embed_model_name.lower() else {}
    embeddings = embed_model.encode(texts, normalize_embeddings=True, **encode_kwargs)
    collection.add(
        ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings.tolist()
    )
    console.print(f"[green]✓ Indexed {len(chunks)} chunks.[/green]")

    # 3. Pre-retrieve Candidates
    console.print("[dim]Running initial retrieval for all queries...[/dim]")
    candidates = []
    found_in_initial = 0

    for test in RETRIEVAL_BENCHMARK:
        query = test["query"]
        expected = test["expected_id"]
        vendor = test["vendor"]

        query_embedding = embed_model.encode(
            [query], normalize_embeddings=True, **encode_kwargs
        ).tolist()
        results = collection.query(
            query_embeddings=query_embedding, n_results=20, where={"vendor": vendor}
        )

        doc_ids = results["ids"][0]
        is_found = expected in doc_ids
        if is_found:
            found_in_initial += 1

        candidates.append(
            {
                "query": query,
                "expected": expected,
                "doc_texts": results["documents"][0],
                "doc_ids": doc_ids,
                "found_initially": is_found,
            }
        )

    recall_at_20 = found_in_initial / len(RETRIEVAL_BENCHMARK)
    console.print(
        f"[bold yellow]Initial Retrieval Recall@20: {recall_at_20:.2f}[/bold yellow]"
    )
    if recall_at_20 < 1.0:
        console.print(
            f"[red]⚠ Warning: Embedder only found the correct doc in {found_in_initial}/{len(RETRIEVAL_BENCHMARK)} cases.[/red]"
        )

    # Clean up embedder from memory if not needed further
    del embed_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return candidates


def run_rerank_test(reranker_model_name, candidates):
    console.print(
        f"\n[bold cyan]>>> Testing Reranker: {reranker_model_name}[/bold cyan]"
    )

    # 1. Load Reranker
    console.print(
        f"[bold magenta]>>> Downloading/Loading Reranker on {DEVICE}...[/bold magenta]"
    )
    start_time = time.time()
    try:
        reranker = CrossEncoder(
            reranker_model_name, device=DEVICE, trust_remote_code=True
        )
    except Exception as e:
        console.print(f"[red]Failed to load reranker: {e}[/red]")
        return None
    reranker_load_time = time.time() - start_time
    console.print(f"[green]✓ Reranker loaded in {reranker_load_time:.1f}s[/green]")

    # 2. Run Reranking Benchmark
    mrr_scores = []
    inference_times = []

    for cand in candidates:
        query = cand["query"]
        expected = cand["expected"]
        doc_texts = cand["doc_texts"]
        doc_ids = cand["doc_ids"]

        # Batch rerank all candidates for this query
        pairs = [[query, doc] for doc in doc_texts]

        start_inf = time.time()
        scores = reranker.predict(pairs, batch_size=32, show_progress_bar=False)
        inference_times.append(time.time() - start_inf)

        # Sort by scores
        ranked_indices = np.argsort(scores)[::-1]
        sorted_ids = [doc_ids[i] for i in ranked_indices]

        # Calculate MRR
        try:
            rank = sorted_ids.index(expected) + 1
            mrr_scores.append(1.0 / rank)
        except ValueError:
            mrr_scores.append(0.0)

    # Cleanup memory
    del reranker
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "mrr": np.mean(mrr_scores),
        "load_time": reranker_load_time,
        "avg_inf_time": np.mean(inference_times),
    }


if __name__ == "__main__":
    global_cleanup()
    CHUNKS_PATH = "data/processed_chunks/all_chunks.json"
    EMBED_MODEL = "ibm-granite/granite-embedding-311m-multilingual-r2"
    RERANKERS = [
        "jinaai/jina-reranker-v2-base-multilingual",
        "jinaai/jina-reranker-v3",
        "mixedbread-ai/mxbai-rerank-base-v1",
        "BAAI/bge-reranker-v2-m3",
        "Alibaba-NLP/gte-reranker-modernbert-base",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "BAAI/bge-reranker-base",
    ]

    # Prepare once
    candidates = prepare_candidates(EMBED_MODEL, CHUNKS_PATH)

    if not candidates:
        console.print("[red]Failed to prepare candidates. Exiting.[/red]")
        sys.exit(1)

    results = {}
    for reranker in RERANKERS:
        results[reranker] = run_rerank_test(reranker, candidates)

    table = Table(title=f"Reranker Model Comparison (with {EMBED_MODEL})")
    table.add_column("Reranker Model", style="cyan")
    table.add_column("Mean MRR", justify="right", style="green")
    table.add_column("Avg Inf Time (s)", justify="right", style="yellow")
    table.add_column("Load Time (s)", justify="right", style="magenta")

    for model, res in results.items():
        if res:
            table.add_row(
                model,
                f"{res['mrr']:.4f}",
                f"{res['avg_inf_time']:.3f}",
                f"{res['load_time']:.1f}",
            )

    console.print(table)
