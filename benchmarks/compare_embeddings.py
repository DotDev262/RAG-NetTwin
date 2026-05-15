import sys
import json
import numpy as np
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from rich.console import Console
from rich.table import Table

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.utils import calculate_mrr, calculate_ndcg

console = Console()

RETRIEVAL_BENCHMARK = [
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
    {
        "query": "how to set the LISP map-cache limit to 5000 entries",
        "vendor": "cisco",
        "expected_id": "chunk_000053",
    },
    {
        "query": "show ospf database external detail command on junos",
        "vendor": "juniper",
        "expected_id": "chunk_000105",
    },
    {
        "query": "difference between LISP proxy-itrs and proxy-etrs implementation",
        "vendor": "cisco",
        "expected_id": "chunk_000054",
    },
    {
        "query": "troubleshoot lisp registration failures and timeout events",
        "vendor": "cisco",
        "expected_id": "chunk_000055",
    },
    {
        "query": "define a routing policy term with community and local-preference",
        "vendor": "juniper",
        "expected_id": "chunk_000110",
    },
    {
        "query": "catalyst 9300 stackwise-virtual configuration requirements",
        "vendor": "cisco",
        "expected_id": "chunk_000200",
    },
    {
        "query": "show lisp site detail vs show lisp site summary",
        "vendor": "cisco",
        "expected_id": "chunk_000056",
    },
]


def run_test(model_name, chunks_path):
    console.print(f"\n[bold yellow]Testing Model: {model_name}[/bold yellow]")

    # 1. Load Model
    start_time = time.time()
    try:
        # Pass default task for models that require it (like Jina v5)
        model = SentenceTransformer(
            model_name,
            trust_remote_code=True,
            model_kwargs={"default_task": "retrieval"}
            if "jina" in model_name.lower()
            else {},
        )
    except Exception as e:
        console.print(f"[red]Failed to load model {model_name}: {e}[/red]")
        return None
    model_load_time = time.time() - start_time

    # 2. Setup Temp Chroma
    db_path = f"./data/tmp_chroma_{hash(model_name)}"
    client = chromadb.PersistentClient(
        path=db_path, settings=Settings(anonymized_telemetry=False)
    )

    # Ensure fresh collection
    collection_name = "test_collection"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"}
    )

    # 3. Load and Index Chunks (Optimized for speed)
    with open(chunks_path, "r") as f:
        all_chunks = json.load(f)

    # Filter: Keep expected chunks and a random sample for noise
    expected_ids = {test["expected_id"] for test in RETRIEVAL_BENCHMARK}
    relevant_chunks = [c for c in all_chunks if c["id"] in expected_ids]
    # Match Colab noise level
    noise_chunks = [c for c in all_chunks if c["id"] not in expected_ids][:500]
    chunks = relevant_chunks + noise_chunks

    console.print(
        f"[dim]Indexing {len(chunks)} chunks ({len(relevant_chunks)} expected + {len(noise_chunks)} noise)...[/dim]"
    )

    # Index in batches
    batch_size = 100
    index_start = time.time()

    # Handle Granite instructions (matching Colab logic)
    is_granite = "granite" in model_name.lower()
    doc_prefix = (
        "Instruction: Given a network documentation chunk, extract and embed it for retrieval.\nChunk: "
        if is_granite
        else ""
    )
    query_prefix = (
        "Instruction: Given a network engineering query, retrieve the most relevant command documentation.\nQuery: "
        if is_granite
        else ""
    )

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [doc_prefix + c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = [{"vendor": c["vendor"]} for c in batch]

        # Jina v5 uses 'retrieval' for both
        encode_kwargs = {"task": "retrieval"} if "jina" in model_name.lower() else {}
        embeddings = model.encode(texts, normalize_embeddings=True, **encode_kwargs)
        collection.add(
            ids=ids,
            documents=[c["text"] for c in batch],  # Original text in docs
            metadatas=metadatas,
            embeddings=embeddings.tolist(),
        )
    index_time = time.time() - index_start

    # 4. Run Benchmark
    mrr_scores = []
    ndcg_scores = []

    for test in RETRIEVAL_BENCHMARK:
        query = query_prefix + test["query"]
        expected = test["expected_id"]
        vendor = test["vendor"]

        # Query: Jina v5 uses 'retrieval'
        query_encode_kwargs = (
            {"task": "retrieval"} if "jina" in model_name.lower() else {}
        )
        query_embedding = model.encode(
            [query], normalize_embeddings=True, **query_encode_kwargs
        ).tolist()
        results = collection.query(
            query_embeddings=query_embedding, n_results=10, where={"vendor": vendor}
        )

        retrieved_ids = results["ids"][0]
        mrr_scores.append(calculate_mrr(expected, retrieved_ids))
        ndcg_scores.append(calculate_ndcg(expected, retrieved_ids))

    # Cleanup
    import shutil

    shutil.rmtree(db_path, ignore_errors=True)

    return {
        "mrr": np.mean(mrr_scores),
        "ndcg": np.mean(ndcg_scores),
        "load_time": model_load_time,
        "index_time": index_time,
    }


if __name__ == "__main__":
    CHUNKS_PATH = "data/processed_chunks/all_chunks.json"
    MODELS = [
        "BAAI/bge-small-en-v1.5",
        "Alibaba-NLP/gte-modernbert-base",
        "ibm-granite/granite-embedding-311m-multilingual-r2",
        "answerdotai/ModernBERT-base-veblen-retrieval",
    ]

    results = {}
    for model in MODELS:
        results[model] = run_test(model, CHUNKS_PATH)

    # Final Table
    table = Table(title="Embedding Model Comparison")
    table.add_column("Model", style="cyan")
    table.add_column("Mean MRR", justify="right", style="green")
    table.add_column("Mean NDCG", justify="right", style="green")
    table.add_column("Index Time (s)", justify="right")

    for model, metrics in results.items():
        if metrics:
            table.add_row(
                model,
                f"{metrics['mrr']:.4f}",
                f"{metrics['ndcg']:.4f}",
                f"{metrics['index_time']:.1f}",
            )

    console.print(table)
