import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any
import json
import os
from dotenv import load_dotenv

load_dotenv()

class VectorStore:
    """Manages ChromaDB vector database for RAG"""
    
    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
            
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="cisco_commands",
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"Connected to ChromaDB at {self.persist_dir}")
        print(f"Collection 'cisco_commands' ready")
    
    def add_chunks(self, chunks: List[Any]):
        """
        Add chunks to vector database.
        Expects a list of objects with attributes: id, text, tier, vendor, os_version, etc.
        """
        if not chunks:
            return
            
        documents = []
        metadatas = []
        ids = []
        
        for chunk in chunks:
            documents.append(chunk.text)
            metadatas.append({
                'tier': chunk.tier,
                'vendor': chunk.vendor,
                'os_version': chunk.os_version,
                'command_hierarchy': json.dumps(chunk.command_hierarchy),
                'context_tags': json.dumps(chunk.context_tags),
                'source_file': chunk.source_file,
                'page_range': json.dumps(chunk.page_range)
            })
            ids.append(chunk.id)
        
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"Added {len(chunks)} chunks to vector database")
    
    def retrieve(self, query: str, os_version: str = None, tier: int = None, n_results: int = 5) -> List[Dict]:
        """
        Retrieve relevant chunks for a query
        
        Args:
            query: Search query
            os_version: Filter by OS version (e.g., "ios-xe-17.6")
            tier: Filter by tier (1, 2, or 3)
            n_results: Number of results to return
        """
        # Build where clause for filtering
        where_clause = {}
        if os_version:
            where_clause["os_version"] = os_version
        if tier:
            where_clause["tier"] = tier
        
        # Query collection
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause if where_clause else None
        )
        
        # Format results
        formatted_results = []
        if not results['ids'] or not results['ids'][0]:
            return formatted_results
            
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            })
        
        return formatted_results
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        count = self.collection.count()
        return {
            'total_chunks': count,
            'collection_name': self.collection.name
        }

if __name__ == "__main__":
    # Simple test
    store = VectorStore()
    print(f"Stats: {store.get_stats()}")
