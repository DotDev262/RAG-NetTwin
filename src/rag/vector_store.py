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
    from rag.vector_store import VectorStore

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

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import os
import hashlib
import re
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from config import settings
from utils import setup_logger

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

    def __init__(self, persist_dir: str = None):
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

        # Initialize embedding function using sentence-transformers
        # This converts text into dense vectors for semantic search
        sentence_transformer_ef = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model_name
            )
        )

        # Get or create collection for documentation
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=sentence_transformer_ef,
        )

        # Get or create collection for few-shot intent parsing examples (Recommendation 2)
        self.few_shot_collection = self.client.get_or_create_collection(
            name="intent_few_shot",
            metadata={"hnsw:space": "cosine"},
            embedding_function=sentence_transformer_ef,
        )

        # Get or create collection for Semantic Cache (Recommendation 5)
        self.cache_collection = self.client.get_or_create_collection(
            name="intent_cache",
            metadata={"hnsw:space": "cosine"},
            embedding_function=sentence_transformer_ef,
        )

        # Hybrid Search: BM25 components
        self.bm25 = None
        self.corpus_map = {} # chunk_id -> chunk_data
        self._initialize_bm25()

        # Reranker: Cross-Encoder (Recommendation 1 Elite)
        try:
            self.reranker = CrossEncoder(settings.reranker_model_name)
            print(f"Reranker initialized: {settings.reranker_model_name}")
        except Exception as e:
            print(f"Failed to initialize Reranker: {e}")
            self.reranker = None

        print(f"Connected to ChromaDB at {self.persist_dir}")
        print(f"Collection '{settings.collection_name}' ready")

    def _initialize_bm25(self):
        """
        Builds the BM25 index from current ChromaDB contents.
        """
        try:
            # Fetch ALL chunks for the BM25 index
            all_data = self.collection.get()
            if not all_data["ids"]:
                return

            tokenized_corpus = []
            for i in range(len(all_data["ids"])):
                chunk_id = all_data["ids"][i]
                text = all_data["documents"][i]
                metadata = all_data["metadatas"][i]
                
                # Store in map for fast lookup during retrieval
                self.corpus_map[chunk_id] = {
                    "id": chunk_id,
                    "text": text,
                    "metadata": metadata
                }
                
                # Tokenize for BM25 (simple whitespace + punctuation split)
                tokenized_corpus.append(text.lower().split())

            self.bm25 = BM25Okapi(tokenized_corpus)
            print(f"BM25 Index initialized with {len(tokenized_corpus)} documents.")
        except Exception as e:
            print(f"Failed to initialize BM25: {e}")

    def add_chunks(self, chunks: List[Any], batch_size: int = 5000):
        """
        Add chunks to vector database in batches.

        This method processes chunks in configurable batch sizes to avoid
        memory issues with large ingestion. Each chunk should be an object
        with text and metadata attributes.

        Args:
            chunks: List of chunk objects with attributes:
                - text: The document text content
                - tier: Hierarchical level (1, 2, or 3)
                - vendor: Device vendor
                - os_version: OS version string
                - command_hierarchy: Parent command path
                - context_tags: Topic tags
                - source_file: Original source file
                - page_range: PDF page range
                - id: Unique chunk identifier
            batch_size: Number of chunks to process per batch.
                Default is 5000. Adjust based on available memory.

        Returns:
            None. Chunks are added to the ChromaDB collection in place.

        Note:
            This is a destructive operation - chunks are added to the
            collection permanently. Use with caution in production.
        """
        if not chunks:
            return

        total_added = 0
        # Process chunks in batches to avoid memory issues
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            documents = []
            metadatas = []
            ids = []

            # Extract text and metadata from each chunk
            for chunk in batch:
                documents.append(chunk.text)
                metadatas.append(
                    {
                        "tier": chunk.tier,
                        "vendor": chunk.vendor,
                        "os_version": chunk.os_version,
                        "command_hierarchy": json.dumps(chunk.command_hierarchy),
                        "context_tags": json.dumps(chunk.context_tags),
                        "source_file": chunk.source_file,
                        "page_range": json.dumps(chunk.page_range),
                    }
                )
                ids.append(chunk.id)

            # Add batch to collection
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

            total_added += len(batch)
            print(
                f"  Added batch {i // batch_size + 1}: {len(batch)} chunks (total: {total_added})"
            )

        print(f"Added {total_added} chunks to vector database")

    def retrieve(
        self,
        query: str,
        vendor: str = None,
        os_version: str = None,
        tier: int = None,
        n_results: int = 5,
        exact_version: bool = True,
    ) -> List[Dict]:
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
        where_conditions = []
        if vendor:
            where_conditions.append({"vendor": vendor})
        if os_version:
            if exact_version:
                where_conditions.append({"os_version": os_version})
            else:
                # Use $contains to allow "17.6" to match "ios-xe-17.6" (Flaw 2)
                where_conditions.append({"os_version": {"$contains": os_version}})
        if tier:
            where_conditions.append({"tier": tier})

        # Construct the where clause based on number of conditions
        where_clause = None
        if len(where_conditions) == 1:
            # Single condition - use directly
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            # Multiple conditions - combine with $and
            where_clause = {"$and": where_conditions}

        # Query the collection with filters
        results = self.collection.query(
            query_texts=[query], n_results=n_results, where=where_clause
        )

        # Format results into list of dicts
        formatted_results = []
        if not results["ids"] or not results["ids"][0]:
            return formatted_results

        for i in range(len(results["ids"][0])):
            formatted_results.append(
                {
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
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
        
        ids = [hashlib.md5(ex["intent"].encode()).hexdigest() for ex in examples]
        documents = [ex["intent"] for ex in examples]
        metadatas = [{"structured": ex["structured"]} for ex in examples]
        
        self.few_shot_collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"Added {len(examples)} examples to few-shot collection.")

    def retrieve_few_shot(self, query: str, n_results: int = 3) -> List[Dict]:
        """
        Retrieves the most similar intent-to-json examples.
        """
        results = self.few_shot_collection.query(
            query_texts=[query], n_results=n_results
        )
        
        formatted = []
        if not results["ids"] or not results["ids"][0]:
            return formatted
            
        for i in range(len(results["ids"][0])):
            formatted.append({
                "intent": results["documents"][0][i],
                "structured": results["metadatas"][0][i]["structured"]
            })
        return formatted

    def check_cache(self, intent_text: str, parameters: Dict[str, Any], vendor: str, threshold: float = 0.01) -> Optional[Dict]:
        """
        Checks the semantic cache for a matching intent.
        Threshold: 0.01 is highly restrictive (near identical).
        """
        # We include parameters in the query to increase specificity
        query = f"{intent_text} {json.dumps(parameters)}"
        
        results = self.cache_collection.query(
            query_texts=[query], 
            n_results=1,
            where={"vendor": vendor}
        )
        
        if results["ids"] and results["ids"][0] and results["distances"][0][0] <= threshold:
            return json.loads(results["metadatas"][0][0]["response"])
        return None

    def update_cache(self, intent_text: str, parameters: Dict[str, Any], vendor: str, response: Dict[str, Any]):
        """
        Adds a successfully generated configuration to the semantic cache.
        """
        query = f"{intent_text} {json.dumps(parameters)}"
        cache_id = hashlib.md5(f"{vendor}:{query}".encode()).hexdigest()
        
        self.cache_collection.add(
            ids=[cache_id],
            documents=[query],
            metadatas=[{
                "vendor": vendor,
                "response": json.dumps(response)
            }]
        )

    def hybrid_retrieve(
        self,
        query: str,
        vendor: str = None,
        os_version: str = None,
        tier: int = None,
        n_results: int = 5,
        k: int = 60, # RRF constant
        exact_version: bool = True
    ) -> List[Dict]:
        """
        Performs Hybrid Search using Reciprocal Rank Fusion (RRF).
        Combines Semantic (Vector) and Keyword (BM25) results.
        """
        # 1. Try initial retrieval (default: exact version)
        results = self._hybrid_retrieve_internal(query, vendor, os_version, tier, n_results, k, exact_version)
        
        # 2. Fallback: If exact match failed and we have an os_version, try fuzzy major version (Flaw 2)
        if not results and os_version and exact_version:
            # Extract major version (e.g. "17.6" -> "17", "ios-xe-17.6" -> "17")
            # This is a heuristic - we look for the first digits after a hyphen or at start
            version_parts = re.findall(r'\d+', os_version)
            if version_parts:
                major = version_parts[0]
                logger.info(f"Exact match for {os_version} failed. Falling back to major version {major} fuzzy match.")
                results = self._hybrid_retrieve_internal(query, vendor, major, tier, n_results, k, exact_version=False)
                
        return results

    def _hybrid_retrieve_internal(
        self,
        query: str,
        vendor: str = None,
        os_version: str = None,
        tier: int = None,
        n_results: int = 5,
        k: int = 60,
        exact_version: bool = True
    ) -> List[Dict]:
        """Internal hybrid retrieval logic."""
        # 1. Semantic Search (passes exact_version flag)
        vector_results = self.retrieve(query, vendor, os_version, tier, n_results=n_results*2, exact_version=exact_version)
        
        # 2. Keyword Search (BM25)
        if not self.bm25:
            return vector_results # Fallback
            
        tokenized_query = query.lower().split()
        # Get top matching docs from BM25
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Sort BM25 results by score and apply filters manually
        bm25_ranked = []
        all_ids = list(self.corpus_map.keys())
        for idx, score in enumerate(bm25_scores):
            if score > 0:
                chunk_id = all_ids[idx]
                chunk = self.corpus_map[chunk_id]
                
                # Apply metadata filters
                meta = chunk["metadata"]
                if vendor and meta.get("vendor") != vendor: continue
                
                if os_version:
                    chunk_version = str(meta.get("os_version", ""))
                    if exact_version:
                        if chunk_version != os_version: continue
                    else:
                        if os_version not in chunk_version: continue
                        
                if tier and meta.get("tier") != tier: continue
                
                bm25_ranked.append(chunk_id)
        
        bm25_ranked = bm25_ranked[:n_results*2]

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores = {} # id -> rrf_score
        
        # Add vector ranks
        for rank, res in enumerate(vector_results):
            chunk_id = res["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (1.0 / (k + rank + 1))
            
        # Add BM25 ranks
        for rank, chunk_id in enumerate(bm25_ranked):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (1.0 / (k + rank + 1))
            
        # 4. Final Ranking
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        final_results = []
        for chunk_id in sorted_ids[:n_results]:
            chunk = self.corpus_map[chunk_id]
            final_results.append({
                "id": chunk["id"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "rrf_score": rrf_scores[chunk_id]
            })
            
        return final_results

    def rerank(self, query: str, chunks: List[Dict], n_results: int = 1) -> List[Dict]:
        """
        Uses the local Cross-Encoder to re-score and rank chunks.
        """
        if not self.reranker or not chunks:
            return chunks[:n_results]

        # Prepare pairs for the Cross-Encoder: (Query, Document)
        pairs = [[query, chunk["text"]] for chunk in chunks]
        
        # Get scores (higher is better)
        scores = self.reranker.predict(pairs)
        
        # Attach scores to chunks and sort
        for i, score in enumerate(scores):
            chunks[i]["rerank_score"] = float(score)
            
        ranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:n_results]

    def retrieve_with_parents(self, results: List[Dict]) -> List[Dict]:
        """
        Enhances results by fetching parent documents for any Tier 1 chunks.
        (Recommendation Elite: Knowledge Graph Readiness)
        """
        enhanced_results = list(results)
        parent_ids_to_fetch = []
        
        # 1. Identify parents needed
        for res in results:
            parent_id = res["metadata"].get("parent_id")
            if parent_id and parent_id != "":
                # Check if parent is already in the results
                if not any(r["id"] == parent_id for r in enhanced_results):
                    parent_ids_to_fetch.append(parent_id)
        
        # 2. Fetch parents from the corpus map (fast lookup)
        if parent_ids_to_fetch and self.corpus_map:
            logger.info(f"Fetching {len(parent_ids_to_fetch)} parent documents for grounding path...")
            for pid in set(parent_ids_to_fetch):
                if pid in self.corpus_map:
                    parent_chunk = self.corpus_map[pid]
                    # Tag as parent for LLM transparency
                    parent_chunk["metadata"]["is_parent_context"] = True
                    enhanced_results.append(parent_chunk)
                    
        return enhanced_results

    def get_stats(self) -> Dict:
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
        count = self.collection.count()
        return {"total_chunks": count, "collection_name": self.collection.name}


if __name__ == "__main__":
    # Simple test of the vector store
    store = VectorStore()
    print(f"Stats: {store.get_stats()}")
