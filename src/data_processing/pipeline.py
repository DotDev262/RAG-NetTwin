from pathlib import Path
import json
import sys
import os

# Add src to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_processing.pdf_extractor import extract_text_from_pdf
from data_processing.chunker import HierarchicalChunker
from rag.vector_store import VectorStore

def process_documentation():
    """
    Complete pipeline: PDF → Chunks → ChromaDB
    """
    print("=" * 60)
    print("CISCO DOCUMENTATION PROCESSING PIPELINE")
    print("=" * 60)
    
    # Step 1: Load document index
    index_path = Path("data/doc_index.json")
    if not index_path.exists():
        print(f"Error: Document index not found at {index_path}")
        print("Please create data/doc_index.json first.")
        return
        
    with open(index_path, 'r') as f:
        documents = json.load(f)
    
    print(f"\nFound {len(documents)} documents to process")
    
    # Step 2: Initialize chunker and vector store
    store = VectorStore()
    
    all_chunks = []
    global_chunk_counter = 0
    
    # Step 3: Process each document
    for doc in documents:
        print(f"\nProcessing: {doc['title']}")
        file_path = doc['file_path']
        
        if not Path(file_path).exists():
            print(f"  ✗ Skipping: File not found at {file_path}")
            continue
            
        # Initialize chunker for this doc's version
        chunker = HierarchicalChunker(vendor=doc['vendor'], os_version=doc['os_version'])
        
        # Extract text based on file extension
        if file_path.endswith('.pdf'):
            pages = extract_text_from_pdf(file_path)
            print(f"  ✓ Extracted {len(pages)} pages from PDF")
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            # Split by section headers or just treat as a few large chunks
            # For simplicity, treat as one "page" per 5000 chars
            chars_per_page = 5000
            pages = []
            for i in range(0, len(text), chars_per_page):
                pages.append({
                    'page_num': (i // chars_per_page) + 1,
                    'text': text[i:i+chars_per_page],
                    'section_title': doc['title'],
                    'source_file': Path(file_path).name
                })
            print(f"  ✓ Processed text file into {len(pages)} virtual pages")
        else:
            print(f"  ✗ Skipping: Unsupported file type for {file_path}")
            continue
        
        # Create chunks
        chunks = chunker.chunk_document(pages)
        
        # Assign global unique IDs
        for chunk in chunks:
            chunk.id = f"chunk_{global_chunk_counter:06d}"
            global_chunk_counter += 1
            
        print(f"  ✓ Created {len(chunks)} chunks")
        
        # Show tier distribution
        tier_counts = {}
        for chunk in chunks:
            tier_counts[chunk.tier] = tier_counts.get(chunk.tier, 0) + 1
        print(f"  ✓ Tiers: {dict(sorted(tier_counts.items()))}")
        
        all_chunks.extend(chunks)
    
    if not all_chunks:
        print("\nNo chunks created. Pipeline terminating.")
        return
        
    # Step 4: Add to vector database
    print(f"\n{'='*60}")
    print(f"Adding {len(all_chunks)} total chunks to ChromaDB...")
    store.add_chunks(all_chunks)
    
    # Step 5: Verify
    stats = store.get_stats()
    print(f"\n✓ Pipeline complete!")
    print(f"  Total chunks in database: {stats['total_chunks']}")
    
    # Save chunks to file for backup
    chunks_file = Path("data/processed_chunks/all_chunks.json")
    chunks_file.parent.mkdir(exist_ok=True)
    
    # Convert chunks to serializable format
    serializable_chunks = []
    for chunk in all_chunks:
        # Using a dictionary for serialization
        chunk_dict = {
            'id': chunk.id,
            'text': chunk.text,
            'tier': chunk.tier,
            'vendor': chunk.vendor,
            'os_version': chunk.os_version,
            'command_hierarchy': chunk.command_hierarchy,
            'context_tags': chunk.context_tags,
            'source_file': chunk.source_file,
            'page_range': chunk.page_range
        }
        serializable_chunks.append(chunk_dict)
        
    with open(chunks_file, 'w') as f:
        json.dump(serializable_chunks, f, indent=2)
    print(f"  Backup saved to: {chunks_file}")
    
    return all_chunks

if __name__ == "__main__":
    process_documentation()