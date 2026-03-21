import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
from typing import List, Dict, Any
import json
import os
from config import settings


class VectorStore:
    """Manages ChromaDB vector database for RAG"""

    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            persist_dir = settings.chroma_persist_dir

        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir), settings=Settings(anonymized_telemetry=False)
        )

        # Initialize embedding function
        sentence_transformer_ef = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.embedding_model_name
            )
        )

        # Get or create collection
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
        Expects a list of objects with attributes: id, text, tier, vendor, os_version, etc.
        """
        if not chunks:
            return

        total_added = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            documents = []
            metadatas = []
            ids = []

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
        Retrieve relevant chunks for a query

        Args:
            query: Search query
            vendor: Filter by vendor (e.g., "cisco", "juniper")
            os_version: Filter by OS version (e.g., "ios-xe-17.6")
            tier: Filter by tier (1, 2, or 3)
            n_results: Number of results to return
        """
        # Build where clause for filtering
        where_conditions = []
        if vendor:
            where_conditions.append({"vendor": vendor})
        if os_version:
            where_conditions.append({"os_version": os_version})
        if tier:
            where_conditions.append({"tier": tier})

        where_clause = None
        if len(where_conditions) == 1:
            where_clause = where_conditions[0]
        elif len(where_conditions) > 1:
            where_clause = {"$and": where_conditions}

        # Query collection
        results = self.collection.query(
            query_texts=[query], n_results=n_results, where=where_clause
        )

        # Format results
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
        """Get database statistics"""
        count = self.collection.count()
        return {"total_chunks": count, "collection_name": self.collection.name}


if __name__ == "__main__":
    # Simple test
    store = VectorStore()
    print(f"Stats: {store.get_stats()}")
