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
from typing import List, Dict, Any
import json
import os
from config import settings


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

        # Get or create collection with cosine similarity metric
        # Using "cosine" because we're comparing normalized embeddings
        self.collection = self.client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=sentence_transformer_ef,
        )

        print(f"Connected to ChromaDB at {self.persist_dir}")
        print(f"Collection '{settings.collection_name}' ready")

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
            where_conditions.append({"os_version": os_version})
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
