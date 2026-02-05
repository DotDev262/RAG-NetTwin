import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag.vector_store import VectorStore

def test_retrieval():
    """Test RAG retrieval with various queries"""
    store = VectorStore()
    
    test_queries = [
        "How to configure OSPF?",
        "What is the command for ip address?",
        "Show interface status command",
        "How to create an access-list?",
        "Configure VLAN 10"
    ]
    
    print("Testing RAG Retrieval\n")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)
        
        # Retrieve with version lock
        results = store.retrieve(query, os_version="ios-xe-17.6", n_results=3)
        
        if not results:
            print("No results found.")
            continue
            
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result['id']}] Tier {result['metadata']['tier']}")
            print(f"   Source: {result['metadata']['source_file']}")
            print(f"   Distance: {result['distance']:.3f}")
            print(f"   Preview: {result['text'][:150]}...")
            print()

if __name__ == "__main__":
    test_retrieval()