"""
Vector Store Module for RAG-NetTwin.

This module manages the ChromaDB vector database used for Retrieval-Augmented
Generation (RAG). It handles storage and retrieval of network configuration
documentation chunks with vendor and version filtering.

Key Features:
- ChromaDB persistence for local vector storage
- Vendor and OS version filtering for accurate retrieval
- Hierarchical metadata storage (tier, command hierarchy, context tags)
- Sentence transformer embeddings for semantic search

Typical Usage:
    from src.rag.vector_store import VectorStore

    store = VectorStore()

    # Add chunks to database
    store.add_chunks(chunks)

    # Retrieve relevant docs with filters
    results = store.retrieve(
        query="ospf configuration area",
        vendor="cisco",
        os_version="ios-xe-17.6",
        n_results=5
    )
"""

import json
import hashlib
import os
import logging
from typing import List, Dict, Any, Optional, cast
from pathlib import Path

import chromadb
import networkx as nx  # type: ignore
from chromadb.config import Settings
from networkx.readwrite import json_graph  # type: ignore
from rank_bm25 import BM25Okapi  # type: ignore
from sentence_transformers import CrossEncoder

from src.config import settings
from src.utils import setup_logger

from chromadb.utils import embedding_functions

# Suppress transformer and BERT loading reports
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logger = setup_logger("VectorStore")


class VectorStore:
    """
    Manages ChromaDB vector database for RAG.

    This class provides an interface to store network configuration
    documentation as vector embeddings and retrieve them using semantic
    search. It supports filtering by vendor and OS version to ensure
    version-locked retrieval accuracy.

    The vector store stores chunks with rich metadata including:
    - tier: Hierarchical chunk level (1=command, 2=context, 3=example)
    - vendor: Device vendor (e.g., "cisco", "juniper")
    - os_version: OS version (e.g., "ios-xe-17.6", "junos-21.4")
    - command_hierarchy: Parent command path for context
    - context_tags: Topic tags for filtering
    - source_file: Original documentation source
    - page_range: PDF page range for reference

    Attributes:
        persist_dir: Directory path where ChromaDB persists data.
        client: ChromaDB persistent client instance.
        collection: The ChromaDB collection for storing/retrieving chunks.

    Note:
        The embedding model is configured via settings.embedding_model_name
        and defaults to a sentence-transformer model for semantic similarity.
    """

    def __init__(self, persist_dir: Optional[str] = None):
        """
        Initialize the VectorStore.

        Args:
            persist_dir: Optional custom directory for ChromaDB persistence.
                If None, uses settings.chroma_persist_dir.
        """
        if persist_dir is None:
            persist_dir = settings.chroma_persist_dir

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        # anonymized_telemetry=False disables anonymous usage data collection
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir), settings=Settings(anonymized_telemetry=False)
        )

        # Recommendation 2 & 4: Upgraded retrieval with Jina-v5 SOTA stack
        # Using SentenceTransformer directly to handle trust_remote_code more reliably
        from sentence_transformers import SentenceTransformer

        try:
            self.model = SentenceTransformer(
                settings.embedding_model_name, trust_remote_code=True
            )
            # Use retrieval task for Jina models to improve recall
            if "jina" in settings.embedding_model_name.lower():
                self.model.default_task = "retrieval"  # type: ignore[assignment]
            logger.info(f"Loaded embedding model: {settings.embedding_model_name}")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            raise e

        # Create the custom embedding function wrapper
        self.chroma_embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model_name
            )
        )

        # Get or create collection for documentation
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.chroma_embedding_function,  # type: ignore[arg-type]
        )

        # Get or create collection for few-shot intent parsing examples (Recommendation 2)
        self.few_shot_collection = self.client.get_or_create_collection(
            name="intent_few_shot",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.chroma_embedding_function,  # type: ignore[arg-type]
        )

        # Get or create collection for Semantic Cache (Recommendation 5)
        self.cache_collection = self.client.get_or_create_collection(
            name="intent_cache",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.chroma_embedding_function,  # type: ignore[arg-type]
        )

        # Get or create collection for Gold Standard Configs (Recommendation 3 - Phase 2)
        self.gold_configs_collection = self.client.get_or_create_collection(
            name="gold_configs",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.chroma_embedding_function,  # type: ignore[arg-type]
        )

        # Get or create collection for Intent Parsing Cache (Efficiency Phase 1)
        self.intent_parsing_cache_collection = self.client.get_or_create_collection(
            name="intent_parsing_cache",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.chroma_embedding_function,  # type: ignore[arg-type]
        )

        # Hybrid Search: BM25 components
        self.bm25: Optional[BM25Okapi] = None
        self.corpus_map: Dict[str, Dict[str, Any]] = {}  # chunk_id -> chunk_data
        self._initialize_bm25()

        # Reranker: Cross-Encoder (Recommendation 1 Elite)
        self.reranker: Optional[CrossEncoder] = None
        try:
            self.reranker = CrossEncoder(
                settings.reranker_model_name, trust_remote_code=True
            )
            logger.info(f"Reranker initialized: {settings.reranker_model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Reranker: {e}")

        # Knowledge Graph: GraphRAG components (Recommendation 4)
        self.graph: Optional[nx.Graph] = None
        self._load_knowledge_graph()

        print(f"Connected to ChromaDB at {self.persist_dir}")
        print(f"Collection '{settings.collection_name}' ready")

    def _load_knowledge_graph(self) -> None:
        """
        Loads the specialized documentation knowledge graph from the graphify-docs directory.
        """
        # Point to the graphify-docs directory which contains the domain concepts
        base_path = Path("graphify-docs")
        graph_path = base_path / "graph.json"
        # mapping_path is optional; GraphRAG falls back to direct ID matching
        mapping_path = base_path / "chunk_to_node.json"
        labels_path = base_path / ".graphify_labels.json"

        if not graph_path.exists():
            logger.warning(
                f"Knowledge graph not found at {graph_path}. "
                "GraphRAG features (Community-Aware Retrieval) will be disabled. "
                "Run 'graphify update .' to generate the graph."
            )
            return

        try:
            # 1. Load Graph
            with open(graph_path, "r") as f:
                data = json.load(f)
            self.graph = json_graph.node_link_graph(data, edges="links")
            logger.info(
                f"Documentation Knowledge Graph loaded: {self.graph.number_of_nodes()} nodes"
            )

            # 2. Load Mapping (Efficiency Bridge)
            self.chunk_to_node = {}
            if mapping_path.exists():
                with open(mapping_path, "r") as f:
                    self.chunk_to_node = json.load(f)
                logger.info(
                    f"Loaded {len(self.chunk_to_node)} semantic anchors for GraphRAG."
                )

            # 3. Load Community Labels (Semantic Anchors)
            self.community_labels = {}
            if labels_path.exists():
                with open(labels_path, "r") as f:
                    self.community_labels = json.load(f)
                logger.info(
                    f"Loaded {len(self.community_labels)} community labels for GraphRAG."
                )

            # 4. Identify God Nodes (High-degree nodes) dynamically (Fix F15)
            degrees = dict(self.graph.degree())
            if degrees:
                deg_values = sorted(degrees.values())
                # Threshold: nodes in the top 1% of degrees or > 5x the average
                avg_deg = sum(deg_values) / len(deg_values)
                percentile_99 = deg_values[int(len(deg_values) * 0.99)]
                threshold = max(avg_deg * 5, percentile_99)

                self.god_nodes = {
                    node for node, deg in degrees.items() if deg >= threshold
                }
                logger.info(
                    f"Identified {len(self.god_nodes)} 'God Nodes' dynamically (degree >= {threshold:.1f})"
                )
            else:
                self.god_nodes = set()

        except Exception as e:
            logger.error(f"Failed to load documentation knowledge graph: {e}")

    def retrieve_community_context(
        self, seed_chunks: List[Dict[str, Any]], max_additional_chunks: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Community-Aware Retrieval (SOTA GraphRAG):
        Identifies the community clusters of the seed chunks and retrieves the entire cluster.
        This ensures holistic context (e.g., all OSPF related docs) is present.

        Token Efficiency Optimizations:
        1. God Node Pruning: Skips high-degree nodes that bridge unrelated domains.
        2. Community Budgeting: Limits the number of additional chunks to prevent bloat.
        3. Semantic Tagging: Adds community labels to metadata for better grounding.
        """
        if not self.graph:
            return seed_chunks

        community_ids = set()
        for chunk in seed_chunks:
            chunk_id = str(chunk.get("id"))

            # Find the graph node corresponding to this chunk
            node_id = self.chunk_to_node.get(chunk_id)
            if not node_id:
                # If no direct mapping, try using the chunk ID directly as a fallback
                node_id = chunk_id if chunk_id in self.graph else None

            # Token Efficiency: Prune God Nodes from seed expansion
            if (
                node_id
                and node_id in self.graph
                and node_id not in getattr(self, "god_nodes", set())
            ):
                community = self.graph.nodes[node_id].get("community")
                if community is not None:
                    community_ids.add(community)

        # Retrieve all nodes belonging to these communities
        expanded_ids = set()
        for node_id, data in self.graph.nodes(data=True):
            # Token Efficiency: Never expand through God Nodes even if they share a community
            if node_id in getattr(self, "god_nodes", set()):
                continue

            if data.get("community") in community_ids:
                expanded_ids.add(str(node_id))

        final_results = list(seed_chunks)
        # Add all chunks from the discovered communities
        # (This is the 'Context Reach' boost)
        reverse_mapping = {v: k for k, v in self.chunk_to_node.items()}

        added_count = 0
        for nid in expanded_ids:
            # Token Efficiency: Stop once we hit the additional chunk budget
            if added_count >= max_additional_chunks:
                break

            # Map graph node back to Chroma ID
            cid = reverse_mapping.get(nid)
            if cid and cid in self.corpus_map:
                # Avoid duplicates
                if not any(c.get("id") == cid for c in final_results):
                    chunk = self.corpus_map[cid].copy()

                    # Tag with community label for semantic grounding
                    node_data = self.graph.nodes.get(nid, {})
                    comm_id = str(node_data.get("community"))
                    comm_label = self.community_labels.get(comm_id)
                    if comm_label:
                        chunk["metadata"]["graph_community"] = comm_label

                    final_results.append(chunk)
                    added_count += 1

        logger.info(
            f"Community-Aware Expansion: {len(seed_chunks)} seeds -> {len(final_results)} chunks "
            f"(Communities: {list(community_ids)}, Budget: {max_additional_chunks})"
        )
        return final_results

    def _initialize_bm25(self) -> None:
        """
        Builds the BM25 index from current ChromaDB contents.
        """
        try:
            # Fetch ALL chunks for the BM25 index
            all_data = self.collection.get()
            if not all_data or not all_data.get("ids"):
                return

            tokenized_corpus: List[List[str]] = []
            ids: List[str] = cast(List[str], all_data.get("ids") or [])
            documents: List[str] = cast(List[str], all_data.get("documents") or [])
            metadatas: List[Dict[str, Any]] = cast(
                List[Dict[str, Any]], all_data.get("metadatas") or []
            )

            for i in range(len(ids)):
                chunk_id: str = ids[i]
                text: str = documents[i]
                metadata: Dict[str, Any] = metadatas[i]

                # Store in map for fast lookup during retrieval
                self.corpus_map[chunk_id] = {
                    "id": chunk_id,
                    "text": text,
                    "metadata": metadata,
                }

                # Tokenize for BM25 (simple whitespace + punctuation split)
                tokenized_corpus.append(text.lower().split())

            self.bm25 = BM25Okapi(tokenized_corpus)
            print(f"BM25 Index initialized with {len(tokenized_corpus)} documents.")
        except Exception as e:
            print(f"Failed to initialize BM25: {e}")

    def add_chunks(self, chunks: List[Any], batch_size: int = 1000) -> None:
        """
        Add chunks to vector database in batches with CPU throttling.

        Args:
            chunks: List of chunk objects/dicts.
            batch_size: Chunks per batch (default 1000 for lower memory/CPU pressure).
        """
        if not chunks:
            return

        import torch
        from tqdm import tqdm

        # Use all available CPU threads for maximum performance
        original_threads = torch.get_num_threads()
        # torch.set_num_threads(max(1, original_threads)) # Use default full allocation

        total_added = 0
        logger.info(
            f"High-performance bulk indexing: {len(chunks)} chunks using {original_threads} threads..."
        )

        # Sort by text length descending so each encode batch has similar-length texts,
        # minimizing wasteful padding to the longest sequence in the batch
        chunks.sort(
            key=lambda c: -len(c.get("text", "") if isinstance(c, dict) else c.text)
        )

        # Process in larger batches for efficiency
        for i in tqdm(
            range(0, len(chunks), batch_size), desc="Bulk Indexing", unit="batch"
        ):
            batch = chunks[i : i + batch_size]

            batch_texts = []
            batch_metas = []
            batch_ids = []

            # Process metadata on the fly to save memory
            for chunk in batch:
                if isinstance(chunk, dict):
                    text = chunk.get("text", "")
                    metas = {
                        "tier": chunk.get("tier", 1),
                        "vendor": chunk.get("vendor", "unknown"),
                        "os_version": chunk.get("os_version", "unknown"),
                        "command_hierarchy": json.dumps(
                            chunk.get("command_hierarchy", [])
                        ),
                        "context_tags": json.dumps(chunk.get("context_tags", [])),
                        "source_file": chunk.get("source_file", "unknown"),
                        "page_range": json.dumps(chunk.get("page_range", [0, 0])),
                    }
                    cid = chunk.get("id", hashlib.md5(text.encode()).hexdigest())
                else:
                    text = chunk.text
                    metas = {
                        "tier": chunk.tier,
                        "vendor": chunk.vendor,
                        "os_version": chunk.os_version,
                        "command_hierarchy": json.dumps(chunk.command_hierarchy),
                        "context_tags": json.dumps(chunk.context_tags),
                        "source_file": chunk.source_file,
                        "page_range": chunk.page_range,
                        "id": chunk.id,
                    }
                    cid = chunk.id

                batch_texts.append(text)
                batch_metas.append(metas)
                batch_ids.append(cid)

            # Generate embeddings with sorted-length batching to minimize padding waste
            # Texts are pre-sorted by length, so each encode batch has similar-length texts
            # batch_size=4 keeps per-batch sequence lengths manageable on CPU
            is_granite = "granite" in settings.embedding_model_name.lower()
            doc_prefix = (
                "Instruction: Given a network documentation chunk, extract and embed it for retrieval.\nChunk: "
                if is_granite
                else ""
            )

            processed_texts = [doc_prefix + t for t in batch_texts]
            embeddings = self.model.encode(
                processed_texts,
                batch_size=4,
                show_progress_bar=True,
                convert_to_numpy=True,
            ).tolist()

            # Bulk add to Chroma
            self.collection.add(
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=cast(Any, batch_metas),
                ids=batch_ids,
            )

            total_added += len(batch_texts)

        logger.info(f"Successfully indexed {total_added} chunks.")

    def retrieve(
        self,
        query: str,
        vendor: Optional[str] = None,
        os_version: Optional[str] = None,
        tier: Optional[int] = None,
        n_results: int = 5,
        exact_version: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.

        This is the core retrieval method used during RAG. It performs
        semantic search on the vector database with optional filtering
        by vendor, OS version, and tier.

        The retrieval uses cosine similarity to find the most similar
        chunks to the query vector. Results are returned in descending
        order of relevance.

        Args:
            query: Natural language search query (e.g., "ospf area configuration").
            vendor: Optional filter for device vendor (e.g., "cisco", "juniper").
                If None, retrieves from all vendors.
            os_version: Optional filter for OS version (e.g., "ios-xe-17.6").
                If None, retrieves from all versions.
            tier: Optional filter for chunk tier (1, 2, or 3).
                If None, retrieves from all tiers.
            n_results: Number of results to return. Default is 5.
                Higher values return more context but increase token usage.
            exact_version: If True, uses exact match for os_version.
                If False, uses $contains for fuzzy match (Recommendation 7).

        Returns:
            List of result dictionaries, each containing:
                - id: Chunk identifier
                - text: Document text content
                - metadata: Dict with tier, vendor, os_version, etc.
                - distance: Cosine distance score (lower = more similar)

            Returns empty list if no results found.

        Example:
            >>> store = VectorStore()
            >>> results = store.retrieve(
            ...     query="configure BGP neighbor",
            ...     vendor="cisco",
            ...     n_results=3
            ... )
            >>> for r in results:
            ...     print(r['id'], r['distance'])
        """
        # Build where clause for filtering
        # ChromaDB supports $and for combining multiple conditions
        where_conditions: List[Dict[str, Any]] = []
        if vendor:
            where_conditions.append({"vendor": vendor})
        if os_version:
            # Use exact match for os_version ($eq is implicit in Chroma if no operator given)
            where_conditions.append({"os_version": os_version})
        if tier:
            where_conditions.append({"tier": tier})

        # Construct the where clause based on number of conditions
        where_clause: Optional[Dict[str, Any]] = None
        if len(where_conditions) == 1:
            # Single condition - use directly
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            # Multiple conditions - combine with $and
            where_clause = {"$and": where_conditions}

        # Generate query embedding manually with Granite prefix if applicable
        is_granite = "granite" in settings.embedding_model_name.lower()
        processed_query = (
            f"Instruction: Given a network engineering query, retrieve the most relevant command documentation.\nQuery: {query}"
            if is_granite
            else query
        )
        query_embeddings = self.model.encode(
            [processed_query], convert_to_numpy=True
        ).tolist()

        # Query the collection with filters
        results = self.collection.query(
            query_embeddings=query_embeddings, n_results=n_results, where=where_clause
        )

        # Format results into list of dicts
        formatted_results: List[Dict[str, Any]] = []
        ids_list = results.get("ids")
        documents_list = results.get("documents")
        metadatas_list = results.get("metadatas")
        distances_list = results.get("distances")

        if not ids_list or not ids_list[0]:
            return formatted_results

        # Since we only queried one text, we look at the first list of results
        for i in range(len(ids_list[0])):
            formatted_results.append(
                {
                    "id": ids_list[0][i],
                    "text": documents_list[0][i] if documents_list else "",
                    "metadata": metadatas_list[0][i] if metadatas_list else {},
                    "distance": distances_list[0][i] if distances_list else 1.0,
                }
            )

        return formatted_results

    def add_few_shot_examples(self, examples: List[Dict[str, str]]):
        """
        Adds examples to the few-shot collection.
        Each example should have 'intent' (NL) and 'structured' (JSON string).
        """
        if not examples:
            return

        ids: List[str] = [
            hashlib.md5(ex["intent"].encode()).hexdigest() for ex in examples
        ]
        documents: List[str] = [ex["intent"] for ex in examples]
        metadatas: List[Dict[str, Any]] = [
            {"structured": ex["structured"]} for ex in examples
        ]

        # Generate embeddings manually
        embeddings = self.model.encode(documents, convert_to_numpy=True).tolist()

        self.few_shot_collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=cast(Any, metadatas),
        )
        print(f"Added {len(examples)} examples to few-shot collection.")

    def retrieve_few_shot(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves the most similar intent-to-json examples.
        """
        # Generate query embedding manually
        query_embeddings = self.model.encode([query], convert_to_numpy=True).tolist()

        results = self.few_shot_collection.query(
            query_embeddings=query_embeddings, n_results=n_results
        )

        formatted: List[Dict[str, Any]] = []
        ids_list = results.get("ids")
        documents_list = results.get("documents")
        metadatas_list = results.get("metadatas")

        if not ids_list or not ids_list[0]:
            return formatted

        for i in range(len(ids_list[0])):
            metadata = metadatas_list[0][i] if metadatas_list else {}
            doc = documents_list[0][i] if documents_list else ""
            formatted.append(
                {
                    "intent": doc,
                    "structured": metadata.get("structured"),
                }
            )
        return formatted

    def add_gold_configs(self, examples: List[Dict[str, str]]):
        """
        Adds Intent-to-Config examples to the gold standard collection.
        Examples should have 'intent', 'vendor', and 'config'.
        """
        if not examples:
            return

        ids: List[str] = [
            hashlib.md5(f"{ex['vendor']}:{ex['intent']}".encode()).hexdigest()
            for ex in examples
        ]
        documents: List[str] = [ex["intent"] for ex in examples]
        metadatas: List[Dict[str, Any]] = [
            {"vendor": ex["vendor"], "config": ex["config"]} for ex in examples
        ]

        embeddings = self.model.encode(documents, convert_to_numpy=True).tolist()

        self.gold_configs_collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=cast(Any, metadatas),
        )
        print(f"Added {len(examples)} examples to gold standard collection.")

    def retrieve_gold_configs(
        self, query: str, vendor: str, n_results: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the most similar Intent-to-Config examples for a vendor.
        """
        query_embeddings = self.model.encode([query], convert_to_numpy=True).tolist()
        results = self.gold_configs_collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where={"vendor": vendor},
        )

        formatted: List[Dict[str, Any]] = []
        ids_list = results.get("ids")
        documents_list = results.get("documents")
        metadatas_list = results.get("metadatas")

        if not ids_list or not ids_list[0]:
            return formatted

        for i in range(len(ids_list[0])):
            metadata = metadatas_list[0][i] if metadatas_list else {}
            doc = documents_list[0][i] if documents_list else ""
            formatted.append(
                {
                    "intent": doc,
                    "config": metadata.get("config"),
                }
            )
        return formatted

    def check_intent_parsing_cache(
        self, intent_text: str, threshold: float = 0.05
    ) -> Optional[Dict[str, Any]]:
        """
        Efficiency Phase 1: Semantic Intent Cache.
        Checks if a similar intent has already been parsed.
        """
        results = self.intent_parsing_cache_collection.query(
            query_texts=[intent_text], n_results=1
        )

        ids_list = results.get("ids")
        distances_list = results.get("distances")
        metadatas_list = results.get("metadatas")

        if (
            ids_list
            and ids_list[0]
            and distances_list
            and distances_list[0]
            and distances_list[0][0] <= threshold
        ):
            metadata = metadatas_list[0][0] if metadatas_list else None
            if metadata and "structured_intent" in metadata:
                return json.loads(str(metadata["structured_intent"]))
        return None

    def update_intent_parsing_cache(
        self, intent_text: str, structured_intent: Dict[str, Any]
    ) -> None:
        """
        Efficiency Phase 1: Semantic Intent Cache.
        Adds a parsed intent to the semantic cache.
        """
        cache_id = hashlib.md5(intent_text.encode()).hexdigest()
        self.intent_parsing_cache_collection.add(
            ids=[cache_id],
            documents=[intent_text],
            metadatas=[{"structured_intent": json.dumps(structured_intent)}],
        )

    def check_cache(
        self,
        intent_text: str,
        parameters: Dict[str, Any],
        vendor: str,
        retrieval_mode: str = "tiered",
        threshold: float = 0.01,
    ) -> Optional[Dict[str, Any]]:
        """
        Checks the semantic cache for a matching intent, specific to retrieval mode.
        Threshold: 0.01 is highly restrictive (near identical).
        """
        # We include parameters and mode in the query to increase specificity
        query: str = f"Mode: {retrieval_mode} | {intent_text} {json.dumps(parameters)}"

        results = self.cache_collection.query(
            query_texts=[query],
            n_results=1,
            where={"$and": [{"vendor": vendor}, {"retrieval_mode": retrieval_mode}]},
        )

        ids_list = results.get("ids")
        distances_list = results.get("distances")
        metadatas_list = results.get("metadatas")

        if (
            ids_list
            and ids_list[0]
            and distances_list
            and distances_list[0]
            and distances_list[0][0] <= threshold
        ):
            metadata = metadatas_list[0][0] if metadatas_list else None
            if metadata and "response" in metadata:
                return json.loads(str(metadata["response"]))
        return None

    def update_cache(
        self,
        intent_text: str,
        parameters: Dict[str, Any],
        vendor: str,
        response: Dict[str, Any],
        retrieval_mode: str = "tiered",
        version: str = "1.0.0",
    ):
        """
        Adds a successfully generated configuration to the semantic cache.
        """
        query: str = f"Mode: {retrieval_mode} | {intent_text} {json.dumps(parameters)}"
        # Include version in the ID to force invalidation on logic changes
        cache_id: str = hashlib.md5(f"v{version}:{vendor}:{query}".encode()).hexdigest()

        self.cache_collection.add(
            ids=[cache_id],
            documents=[query],
            metadatas=[
                {
                    "vendor": vendor,
                    "response": json.dumps(response),
                    "retrieval_mode": retrieval_mode,
                    "version": version,
                }
            ],
        )

    def clear_cache(self) -> None:
        """
        Purges all entries from the semantic and intent parsing cache collections.
        """
        for coll_name, coll in [
            ("Semantic Cache", self.cache_collection),
            ("Intent Parsing Cache", self.intent_parsing_cache_collection),
        ]:
            try:
                ids_result = coll.get()
                ids: Optional[List[str]] = ids_result.get("ids")
                if ids:
                    coll.delete(ids=ids)
                    logger.info(f"Purged {len(ids)} entries from {coll_name}.")
            except Exception as e:
                logger.warning(f"Failed to clear {coll_name}: {e}")

    def hybrid_retrieve(
        self,
        query: str,
        vendor: Optional[str] = None,
        os_version: Optional[str] = None,
        tier: Optional[int] = None,
        n_results: int = 5,
        k: int = 60,  # RRF constant
    ) -> List[Dict[str, Any]]:
        """
        Performs Hybrid Search using Reciprocal Rank Fusion (RRF).
        Combines Semantic (Vector) and Keyword (BM25) results.
        """
        return self._hybrid_retrieve_internal(
            query, vendor, os_version, tier, n_results, k
        )

    def _hybrid_retrieve_internal(
        self,
        query: str,
        vendor: Optional[str] = None,
        os_version: Optional[str] = None,
        tier: Optional[int] = None,
        n_results: int = 5,
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Internal hybrid retrieval logic."""
        # 1. Semantic Search
        vector_results: List[Dict[str, Any]] = self.retrieve(
            query, vendor, os_version, tier, n_results=n_results * 2
        )

        # 2. Keyword Search (BM25)
        if not self.bm25:
            return vector_results  # Fallback

        tokenized_query: List[str] = query.lower().split()
        # Get top matching docs from BM25
        bm25_scores = self.bm25.get_scores(tokenized_query)

        # Sort BM25 results by score and apply filters manually
        bm25_ranked: List[str] = []
        all_ids: List[str] = list(self.corpus_map.keys())
        for idx, score in enumerate(bm25_scores):
            if score > 0:
                chunk_id: str = all_ids[idx]
                chunk: Dict[str, Any] = self.corpus_map[chunk_id]

                # Apply metadata filters
                meta: Dict[str, Any] = chunk["metadata"]
                if vendor and meta.get("vendor") != vendor:
                    continue

                if os_version:
                    chunk_version: str = str(meta.get("os_version", ""))
                    if os_version not in chunk_version and chunk_version != os_version:
                        continue

                if tier and meta.get("tier") != tier:
                    continue

                bm25_ranked.append(chunk_id)

        bm25_ranked = bm25_ranked[: n_results * 2]

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}  # id -> rrf_score
        vector_distances: Dict[str, float] = {}  # id -> distance

        # Add vector ranks
        for rank, res in enumerate(vector_results):
            chunk_id_res: str = str(res["id"])
            rrf_scores[chunk_id_res] = rrf_scores.get(chunk_id_res, 0.0) + (
                1.0 / (k + rank + 1)
            )
            vector_distances[chunk_id_res] = res.get("distance", 1.0)

        # Add BM25 ranks
        for rank, chunk_id_bm25 in enumerate(bm25_ranked):
            rrf_scores[chunk_id_bm25] = rrf_scores.get(chunk_id_bm25, 0.0) + (
                1.0 / (k + rank + 1)
            )

        # 4. Final Ranking
        sorted_ids: List[str] = sorted(
            rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
        )

        final_results: List[Dict[str, Any]] = []
        for chunk_id_final in sorted_ids[:n_results]:
            chunk_final: Dict[str, Any] = self.corpus_map[chunk_id_final]
            final_results.append(
                {
                    "id": chunk_final["id"],
                    "text": chunk_final["text"],
                    "metadata": chunk_final["metadata"],
                    "rrf_score": rrf_scores[chunk_id_final],
                    "distance": vector_distances.get(chunk_id_final),
                }
            )

        return final_results

    def rerank(
        self, query: str, chunks: List[Dict[str, Any]], n_results: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Uses the local Cross-Encoder to re-score and rank chunks.
        """
        if not self.reranker or not chunks:
            return chunks[:n_results]

        # Fix F13: Avoid mutating the original chunks list
        processed_chunks = [chunk.copy() for chunk in chunks]

        # Prepare pairs for the Cross-Encoder: (Query, Document)
        pairs: List[List[str]] = [
            [query, str(chunk["text"])] for chunk in processed_chunks
        ]

        # Get scores (higher is better)
        scores = self.reranker.predict(pairs)

        # Attach scores to chunks
        for i, score in enumerate(scores):
            # Base score from Cross-Encoder
            final_score = float(score)

            # Phase 1: Syntax-Aware Reranking (Functional Improvement)
            # Boost chunks that contain explicit configuration syntax
            text_lower = str(processed_chunks[i]["text"]).lower()
            syntax_markers = [
                "(config)#",
                "(config-if)#",
                "router ",
                "interface ",  # Cisco
                "[edit]",
                "set ",
                "edit ",
                "hierarchy",  # Juniper
            ]
            if any(marker in text_lower for marker in syntax_markers):
                final_score *= 1.15

            processed_chunks[i]["rerank_score"] = final_score

        ranked: List[Dict[str, Any]] = sorted(
            processed_chunks, key=lambda x: x.get("rerank_score", 0.0), reverse=True
        )
        return ranked[:n_results]

    def reorder_lost_in_the_middle(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Reorders chunks to put most relevant information at the beginning and end.
        Mitigates LLM 'Lost in the Middle' bias.
        """
        if len(chunks) <= 2:
            return chunks

        res: List[Optional[Dict[str, Any]]] = [None] * len(chunks)
        for i, chunk in enumerate(chunks):
            if i % 2 == 0:
                res[i // 2] = chunk
            else:
                res[-(i // 2 + 1)] = chunk
        return [c for c in res if c is not None]

    def retrieve_with_parents(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enhances results by fetching parent documents for any Tier 1 chunks.
        (Recommendation Elite: Knowledge Graph Readiness)
        """
        enhanced_results: List[Dict[str, Any]] = list(results)
        parent_ids_to_fetch: List[str] = []

        # 1. Identify parents needed
        for res in results:
            metadata: Dict[str, Any] = res.get("metadata", {})
            parent_id: Optional[str] = metadata.get("parent_id")
            if parent_id and parent_id != "":
                # Check if parent is already in the results
                if not any(r["id"] == parent_id for r in enhanced_results):
                    parent_ids_to_fetch.append(parent_id)

        # 2. Fetch parents from the corpus map (fast lookup)
        if parent_ids_to_fetch and self.corpus_map:
            logger.info(
                f"Fetching {len(parent_ids_to_fetch)} parent documents for grounding path..."
            )
            for pid in set(parent_ids_to_fetch):
                if pid in self.corpus_map:
                    parent_chunk: Dict[str, Any] = self.corpus_map[pid]
                    # Tag as parent for LLM transparency
                    parent_chunk["metadata"]["is_parent_context"] = True
                    enhanced_results.append(parent_chunk)

        return enhanced_results

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns basic statistics about the vector store including
        total chunk count and collection name.

        Returns:
            Dict containing:
                - total_chunks: Total number of chunks in the collection
                - collection_name: Name of the ChromaDB collection

        Example:
            >>> store = VectorStore()
            >>> stats = store.get_stats()
            >>> print(f"Total chunks: {stats['total_chunks']}")
        """
        count: int = self.collection.count()
        return {"total_chunks": count, "collection_name": self.collection.name}


if __name__ == "__main__":
    # Simple test of the vector store
    store = VectorStore()
    print(f"Stats: {store.get_stats()}")
