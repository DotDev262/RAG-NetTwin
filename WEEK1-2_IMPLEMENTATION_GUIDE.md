# Phase 1 Implementation Guide: Week 1-2 Setup

**Goal**: Get development environment ready and start data collection
**Timeline**: 2 weeks (14 days)
**Deliverable**: Working environment + 500+ document chunks in ChromaDB

---

## DAY 1-2: Environment Setup

### 1. Install Python 3.10+
```bash
# Check current Python version
python --version

# If not 3.10+, download from python.org or use conda
# Windows: Download from python.org
# Linux/Mac: Use pyenv or conda
```

### 2. Create Project Structure
```bash
# Create main project directory
mkdir -p ~/Projects/ragnet-ibn
cd ~/Projects/ragnet-ibn

# Create subdirectories
mkdir -p data/{raw_docs,processed_chunks,configs}
mkdir -p src/{rag,parser,validation,ui}
mkdir -p tests
mkdir -p notebooks
mkdir -p results

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Create requirements.txt
cat > requirements.txt << EOF
# Core dependencies
langchain>=0.1.0
langchain-community>=0.0.1
chromadb>=0.4.0
sentence-transformers>=2.2.0
openai>=1.0.0
requests>=2.31.0

# Data processing
pypdf>=3.17.0
python-docx>=0.8.11
beautifulsoup4>=4.12.0

# Validation
pybatfish>=2023.0.0
napalm>=4.1.0
pyats>=23.0.0

# Web UI
flask>=3.0.0
flask-cors>=4.0.0

# Utilities
python-dotenv>=1.0.0
tqdm>=4.66.0
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
seaborn>=0.12.0
jupyter>=1.0.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
EOF

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Groq API (Free Tier)
```bash
# 1. Go to https://console.groq.com/
# 2. Create free account
# 3. Generate API key
# 4. Save to .env file

cat > .env << EOF
# Groq API (Free tier: 1M tokens/day)
GROQ_API_KEY=your_api_key_here

# Project settings
PROJECT_NAME=ragnet-ibn
VENDOR=cisco
OS_VERSION=ios-xe-17.6

# ChromaDB settings
CHROMA_PERSIST_DIR=./data/chroma_db

# Validation settings
BATFISH_HOST=localhost
BATFISH_PORT=9997
EOF

# Add .env to .gitignore
echo ".env" >> .gitignore
echo "venv/" >> .gitignore
echo "data/chroma_db/" >> .gitignore
echo "__pycache__/" >> .gitignore
```

### 4. Initialize Git Repository
```bash
git init
git add .
git commit -m "Initial project setup"
```

---

## DAY 3-4: Data Collection

### 1. Download Cisco Documentation

**Option A: Manual Download (Recommended)**
- Go to: https://www.cisco.com/c/en/us/support/ios-nx-os-software/ios-xe-17/products-release-notes-list.html
- Download:
  - Command Reference Guide (PDF)
  - Configuration Guide (PDF)
  - Selected feature guides (OSPF, ACL, Interface)

**Option B: Automated (If available)**
```python
# src/data_collection/download_docs.py
import requests
from pathlib import Path

def download_cisco_docs():
    """Download Cisco IOS-XE documentation"""
    output_dir = Path("data/raw_docs")
    output_dir.mkdir(exist_ok=True)
    
    # Note: You'll need to manually download from Cisco website
    # Automated download may violate terms of service
    
    print("Please manually download:")
    print("1. Cisco IOS-XE 17.6 Command Reference")
    print("2. Cisco IOS-XE 17.6 Configuration Fundamentals")
    print("3. Cisco IOS-XE 17.6 IP Routing: OSPF Configuration")
    print("4. Cisco IOS-XE 17.6 Security: ACL Configuration")
    print(f"\nSave to: {output_dir.absolute()}")

if __name__ == "__main__":
    download_cisco_docs()
```

### 2. Verify Downloads
```bash
# Check downloaded files
ls -la data/raw_docs/

# Expected files:
# - ios-xe-17-6-command-reference.pdf
# - ios-xe-17-6-config-guide.pdf
# - ios-xe-17-6-ospf-guide.pdf
# - ios-xe-17-6-acl-guide.pdf
```

### 3. Create Documentation Index
```python
# src/data_collection/doc_index.py
from pathlib import Path
from dataclasses import dataclass
from typing import List
import json

@dataclass
class Document:
    title: str
    vendor: str
    os_version: str
    file_path: str
    doc_type: str  # 'command_ref', 'config_guide', 'feature_guide'
    total_pages: int = 0

def create_doc_index():
    """Create index of all documentation"""
    raw_docs_dir = Path("data/raw_docs")
    
    documents = [
        Document(
            title="Cisco IOS-XE 17.6 Command Reference",
            vendor="cisco",
            os_version="ios-xe-17.6",
            file_path=str(raw_docs_dir / "ios-xe-17-6-command-reference.pdf"),
            doc_type="command_ref"
        ),
        Document(
            title="Cisco IOS-XE 17.6 Configuration Guide",
            vendor="cisco",
            os_version="ios-xe-17.6",
            file_path=str(raw_docs_dir / "ios-xe-17-6-config-guide.pdf"),
            doc_type="config_guide"
        ),
        # Add more as needed
    ]
    
    # Save index
    index_path = Path("data/doc_index.json")
    with open(index_path, 'w') as f:
        json.dump([doc.__dict__ for doc in documents], f, indent=2)
    
    print(f"Created index with {len(documents)} documents")
    return documents

if __name__ == "__main__":
    create_doc_index()
```

Run it:
```bash
python src/data_collection/doc_index.py
```

---

## DAY 5-7: Document Processing & Chunking

### 1. PDF Text Extraction
```python
# src/data_processing/pdf_extractor.py
import pypdf
from pathlib import Path
from typing import List, Dict
import re

def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract text from PDF with page numbers and metadata
    Returns list of dicts with: page_num, text, section_title
    """
    pages = []
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = pypdf.PdfReader(file)
        
        for page_num, page in enumerate(pdf_reader.pages, 1):
            text = page.extract_text()
            
            # Clean text
            text = clean_text(text)
            
            # Try to identify section title
            section_title = extract_section_title(text)
            
            pages.append({
                'page_num': page_num,
                'text': text,
                'section_title': section_title,
                'source_file': Path(pdf_path).name
            })
    
    return pages

def clean_text(text: str) -> str:
    """Clean extracted text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove page numbers
    text = re.sub(r'\b\d+\s+of\s+\d+\b', '', text)
    # Remove header/footer patterns
    text = re.sub(r'Chapter\s+\d+', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_section_title(text: str) -> str:
    """Try to extract section title from page text"""
    lines = text.split('\n')
    # Usually first few lines contain the section title
    for line in lines[:5]:
        line = line.strip()
        if len(line) > 10 and len(line) < 100:
            # Check if it looks like a title (no commands)
            if not line.startswith(('ip ', 'interface ', 'router ')):
                return line
    return "Unknown Section"

if __name__ == "__main__":
    # Test extraction
    pdf_path = "data/raw_docs/ios-xe-17-6-command-reference.pdf"
    pages = extract_text_from_pdf(pdf_path)
    
    print(f"Extracted {len(pages)} pages")
    print(f"\nFirst page preview:")
    print(pages[0]['text'][:500])
```

### 2. Hierarchical Chunking
```python
# src/data_processing/chunker.py
from typing import List, Dict
import re
from dataclasses import dataclass

@dataclass
class Chunk:
    id: str
    text: str
    tier: int  # 1=Command Syntax, 2=Patterns, 3=Troubleshooting
    vendor: str
    os_version: str
    command_hierarchy: List[str]
    context_tags: List[str]
    source_file: str
    page_range: List[int]

class HierarchicalChunker:
    """
    Chunk documents into three tiers:
    - Tier 1: Command syntax and parameters
    - Tier 2: Configuration examples and patterns
    - Tier 3: Troubleshooting and edge cases
    """
    
    def __init__(self, vendor: str, os_version: str):
        self.vendor = vendor
        self.os_version = os_version
        self.chunk_id_counter = 0
    
    def chunk_document(self, pages: List[Dict]) -> List[Chunk]:
        """Process pages and create hierarchical chunks"""
        chunks = []
        
        # Combine pages into larger sections
        sections = self.identify_sections(pages)
        
        for section in sections:
            # Determine tier based on content
            tier = self.classify_tier(section['text'])
            
            # Extract command hierarchy
            commands = self.extract_commands(section['text'])
            
            # Extract context tags
            tags = self.extract_context_tags(section['text'])
            
            # Create chunk
            chunk = Chunk(
                id=f"chunk_{self.chunk_id_counter:05d}",
                text=section['text'],
                tier=tier,
                vendor=self.vendor,
                os_version=self.os_version,
                command_hierarchy=commands,
                context_tags=tags,
                source_file=section['source_file'],
                page_range=[section['start_page'], section['end_page']]
            )
            
            chunks.append(chunk)
            self.chunk_id_counter += 1
        
        return chunks
    
    def identify_sections(self, pages: List[Dict]) -> List[Dict]:
        """Group pages into logical sections"""
        sections = []
        current_section = {
            'text': '',
            'start_page': pages[0]['page_num'],
            'end_page': pages[0]['page_num'],
            'source_file': pages[0]['source_file'],
            'section_title': pages[0]['section_title']
        }
        
        for i, page in enumerate(pages):
            # Check if this is a new section
            if self.is_new_section(page['section_title'], current_section['section_title']):
                # Save previous section
                if current_section['text']:
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    'text': page['text'],
                    'start_page': page['page_num'],
                    'end_page': page['page_num'],
                    'source_file': page['source_file'],
                    'section_title': page['section_title']
                }
            else:
                # Continue current section
                current_section['text'] += '\n' + page['text']
                current_section['end_page'] = page['page_num']
        
        # Don't forget the last section
        if current_section['text']:
            sections.append(current_section)
        
        return sections
    
    def classify_tier(self, text: str) -> int:
        """Classify chunk into tier based on content"""
        text_lower = text.lower()
        
        # Tier 1 indicators: Command syntax definitions
        tier1_indicators = [
            'syntax:', 'format:', 'command:', 'parameter:',
            'default:', 'mode:', 'usage guidelines'
        ]
        
        # Tier 3 indicators: Troubleshooting
        tier3_indicators = [
            'troubleshooting:', 'problem:', 'issue:', 'error:',
            'debug:', 'verify:', 'check:'
        ]
        
        # Count indicators
        tier1_score = sum(1 for indicator in tier1_indicators if indicator in text_lower)
        tier3_score = sum(1 for indicator in tier3_indicators if indicator in text_lower)
        
        if tier1_score >= 2:
            return 1  # Command Syntax
        elif tier3_score >= 2:
            return 3  # Troubleshooting
        else:
            return 2  # Configuration Patterns (default)
    
    def extract_commands(self, text: str) -> List[str]:
        """Extract command hierarchy from text"""
        commands = []
        
        # Look for command patterns
        # Example: "ip address", "interface GigabitEthernet"
        command_patterns = [
            r'\b(ip\s+\w+)',
            r'\b(interface\s+\w+)',
            r'\b(router\s+\w+)',
            r'\b(access-list\s+\w+)',
            r'\b(route-map\s+\w+)'
        ]
        
        for pattern in command_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            commands.extend(matches)
        
        return list(set(commands))  # Remove duplicates
    
    def extract_context_tags(self, text: str) -> List[str]:
        """Extract context tags from text"""
        text_lower = text.lower()
        tags = []
        
        # Define tag mappings
        tag_mappings = {
            'layer3': ['ip address', 'routing', 'ospf', 'bgp', 'eigrp'],
            'layer2': ['switchport', 'vlan', 'trunk', 'access'],
            'security': ['acl', 'access-list', 'firewall', 'crypto'],
            'management': ['snmp', 'ntp', 'logging', 'aaa'],
            'interface': ['gigabitethernet', 'fastethernet', 'serial'],
            'ipv4': ['ip address', 'ipv4'],
            'ipv6': ['ipv6 address', 'ipv6']
        }
        
        for tag, keywords in tag_mappings.items():
            if any(keyword in text_lower for keyword in keywords):
                tags.append(tag)
        
        return tags
    
    def is_new_section(self, current_title: str, prev_title: str) -> bool:
        """Determine if this is a new section"""
        # Simple heuristic: if title changed significantly
        if current_title == prev_title:
            return False
        
        # Check if titles are substantially different
        current_words = set(current_title.lower().split())
        prev_words = set(prev_title.lower().split())
        
        # If less than 50% word overlap, it's a new section
        if len(current_words & prev_words) / max(len(current_words), len(prev_words)) < 0.5:
            return True
        
        return False

if __name__ == "__main__":
    # Test chunking
    from pdf_extractor import extract_text_from_pdf
    
    pdf_path = "data/raw_docs/ios-xe-17-6-command-reference.pdf"
    pages = extract_text_from_pdf(pdf_path)
    
    chunker = HierarchicalChunker(vendor="cisco", os_version="ios-xe-17.6")
    chunks = chunker.chunk_document(pages[:50])  # Process first 50 pages for testing
    
    print(f"Created {len(chunks)} chunks")
    print(f"\nTier distribution:")
    tier_counts = {}
    for chunk in chunks:
        tier_counts[chunk.tier] = tier_counts.get(chunk.tier, 0) + 1
    for tier, count in sorted(tier_counts.items()):
        print(f"  Tier {tier}: {count} chunks")
    
    # Show sample chunk
    if chunks:
        sample = chunks[0]
        print(f"\nSample chunk (Tier {sample.tier}):")
        print(f"Commands: {sample.command_hierarchy}")
        print(f"Tags: {sample.context_tags}")
        print(f"Text preview: {sample.text[:200]}...")
```

---

## DAY 8-10: ChromaDB Setup

### 1. Initialize ChromaDB
```python
# src/rag/vector_store.py
import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict
import json

class VectorStore:
    """Manages ChromaDB vector database for RAG"""
    
    def __init__(self, persist_dir: str = "./data/chroma_db"):
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
    
    def add_chunks(self, chunks: List):
        """Add chunks to vector database"""
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
    # Test vector store
    store = VectorStore()
    
    # Check stats
    stats = store.get_stats()
    print(f"Database stats: {stats}")
    
    # Test retrieval (if chunks exist)
    if stats['total_chunks'] > 0:
        results = store.retrieve("configure OSPF routing", os_version="ios-xe-17.6")
        print(f"\nRetrieved {len(results)} results for query")
        for i, result in enumerate(results[:3], 1):
            print(f"\n{i}. {result['id']} (distance: {result['distance']:.3f})")
            print(f"   {result['text'][:150]}...")
```

### 2. Pipeline Integration
```python
# src/data_processing/pipeline.py
from pathlib import Path
from pdf_extractor import extract_text_from_pdf
from chunker import HierarchicalChunker
from rag.vector_store import VectorStore
import json

def process_documentation():
    """
    Complete pipeline: PDF → Chunks → ChromaDB
    """
    print("=" * 60)
    print("CISCO DOCUMENTATION PROCESSING PIPELINE")
    print("=" * 60)
    
    # Step 1: Load document index
    with open("data/doc_index.json", 'r') as f:
        documents = json.load(f)
    
    print(f"\nFound {len(documents)} documents to process")
    
    # Step 2: Initialize chunker and vector store
    chunker = HierarchicalChunker(vendor="cisco", os_version="ios-xe-17.6")
    store = VectorStore()
    
    all_chunks = []
    
    # Step 3: Process each document
    for doc in documents:
        print(f"\nProcessing: {doc['title']}")
        
        # Extract text from PDF
        pages = extract_text_from_pdf(doc['file_path'])
        print(f"  ✓ Extracted {len(pages)} pages")
        
        # Create chunks
        chunks = chunker.chunk_document(pages)
        print(f"  ✓ Created {len(chunks)} chunks")
        
        # Show tier distribution
        tier_counts = {}
        for chunk in chunks:
            tier_counts[chunk.tier] = tier_counts.get(chunk.tier, 0) + 1
        print(f"  ✓ Tiers: {dict(sorted(tier_counts.items()))}")
        
        all_chunks.extend(chunks)
    
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
    with open(chunks_file, 'w') as f:
        json.dump([chunk.__dict__ for chunk in all_chunks], f, indent=2)
    print(f"  Backup saved to: {chunks_file}")
    
    return all_chunks

if __name__ == "__main__":
    process_documentation()
```

Run the pipeline:
```bash
python src/data_processing/pipeline.py
```

---

## DAY 11-12: Testing & Verification

### 1. Test RAG Retrieval
```python
# tests/test_rag.py
import sys
sys.path.insert(0, 'src')

from rag.vector_store import VectorStore

def test_retrieval():
    """Test RAG retrieval with various queries"""
    store = VectorStore()
    
    test_queries = [
        "configure interface GigabitEthernet",
        "set up OSPF routing protocol",
        "create access control list",
        "configure static route",
        "set up VLAN 10"
    ]
    
    print("Testing RAG Retrieval\n")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)
        
        # Retrieve with version lock
        results = store.retrieve(query, os_version="ios-xe-17.6", n_results=3)
        
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result['id']}] Tier {result['metadata']['tier']}")
            print(f"   Distance: {result['distance']:.3f}")
            print(f"   Preview: {result['text'][:100]}...")
            print()

if __name__ == "__main__":
    test_retrieval()
```

Run test:
```bash
python tests/test_rag.py
```

### 2. Verify Data Quality
```python
# tests/verify_chunks.py
import json
from pathlib import Path
from collections import Counter

def verify_chunks():
    """Verify quality of processed chunks"""
    
    # Load chunks
    chunks_file = Path("data/processed_chunks/all_chunks.json")
    with open(chunks_file, 'r') as f:
        chunks = json.load(f)
    
    print("CHUNK QUALITY VERIFICATION")
    print("=" * 60)
    print(f"Total chunks: {len(chunks)}\n")
    
    # Tier distribution
    tier_counts = Counter(chunk['tier'] for chunk in chunks)
    print("Tier Distribution:")
    for tier, count in sorted(tier_counts.items()):
        pct = (count / len(chunks)) * 100
        print(f"  Tier {tier}: {count} chunks ({pct:.1f}%)")
    
    # Command coverage
    all_commands = []
    for chunk in chunks:
        commands = json.loads(chunk['command_hierarchy'])
        all_commands.extend(commands)
    
    command_counts = Counter(all_commands)
    print(f"\nTop 10 Commands:")
    for cmd, count in command_counts.most_common(10):
        print(f"  {cmd}: {count} chunks")
    
    # Chunk size statistics
    chunk_lengths = [len(chunk['text']) for chunk in chunks]
    avg_length = sum(chunk_lengths) / len(chunk_lengths)
    print(f"\nChunk Size Statistics:")
    print(f"  Average: {avg_length:.0f} characters")
    print(f"  Min: {min(chunk_lengths)} characters")
    print(f"  Max: {max(chunk_lengths)} characters")
    
    # Quality checks
    print(f"\nQuality Checks:")
    empty_chunks = sum(1 for chunk in chunks if len(chunk['text']) < 50)
    print(f"  Empty/very short chunks: {empty_chunks}")
    
    no_commands = sum(1 for chunk in chunks if not json.loads(chunk['command_hierarchy']))
    print(f"  Chunks without commands: {no_commands}")
    
    print("\n✓ Verification complete!")

if __name__ == "__main__":
    verify_chunks()
```

---

## DAY 13-14: Documentation & Checkpoint

### 1. Create README
```markdown
# Week 1-2: Data Collection & RAG Pipeline

## What Was Completed
- [x] Environment setup (Python, dependencies)
- [x] Downloaded Cisco IOS-XE 17.6 documentation
- [x] PDF text extraction pipeline
- [x] Hierarchical chunking (Tier 1, 2, 3)
- [x] ChromaDB vector database setup
- [x] Version-locked retrieval system
- [x] Tests and verification

## Key Files
- `src/data_processing/pdf_extractor.py` - PDF text extraction
- `src/data_processing/chunker.py` - Hierarchical chunking
- `src/rag/vector_store.py` - ChromaDB interface
- `src/data_processing/pipeline.py` - Complete processing pipeline

## Statistics
- Total documents: X
- Total chunks: X (aim for 500+)
- Tier 1 (Syntax): X%
- Tier 2 (Patterns): X%
- Tier 3 (Troubleshooting): X%

## How to Run
```bash
# Setup
pip install -r requirements.txt

# Process documentation
python src/data_processing/pipeline.py

# Test retrieval
python tests/test_rag.py

# Verify chunks
python tests/verify_chunks.py
```

## Next Steps (Week 3-4)
- Intent parser implementation
- LLM integration
- Configuration generation
```

### 2. Create Checkpoint Script
```python
# scripts/checkpoint_week2.py
"""
Week 2 Checkpoint Verification
Run this to verify everything is set up correctly
"""

import sys
from pathlib import Path

def check_requirements():
    """Check all requirements for Week 2 completion"""
    checks = []
    
    # Check 1: Virtual environment
    checks.append(("Virtual environment", Path("venv").exists()))
    
    # Check 2: Dependencies
    try:
        import chromadb
        import langchain
        import pypdf
        checks.append(("Dependencies installed", True))
    except ImportError:
        checks.append(("Dependencies installed", False))
    
    # Check 3: Documentation downloaded
    docs_dir = Path("data/raw_docs")
    pdf_files = list(docs_dir.glob("*.pdf"))
    checks.append(("Documentation downloaded", len(pdf_files) > 0))
    
    # Check 4: ChromaDB initialized
    chroma_dir = Path("data/chroma_db")
    checks.append(("ChromaDB initialized", chroma_dir.exists()))
    
    # Check 5: Chunks created
    chunks_file = Path("data/processed_chunks/all_chunks.json")
    if chunks_file.exists():
        import json
        with open(chunks_file) as f:
            chunks = json.load(f)
        checks.append(("Chunks created", len(chunks) > 100))
        checks.append(("Target: 500+ chunks", len(chunks) >= 500))
        chunk_count = len(chunks)
    else:
        checks.append(("Chunks created", False))
        checks.append(("Target: 500+ chunks", False))
        chunk_count = 0
    
    # Check 6: Can retrieve
    try:
        sys.path.insert(0, 'src')
        from rag.vector_store import VectorStore
        store = VectorStore()
        stats = store.get_stats()
        checks.append(("Vector store accessible", True))
        checks.append(("Chunks in database", stats['total_chunks'] > 0))
    except Exception as e:
        checks.append(("Vector store accessible", False))
        checks.append(("Chunks in database", False))
    
    # Print results
    print("=" * 60)
    print("WEEK 2 CHECKPOINT VERIFICATION")
    print("=" * 60)
    
    passed = 0
    for check_name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {check_name}")
        if result:
            passed += 1
    
    print("=" * 60)
    print(f"Passed: {passed}/{len(checks)}")
    
    if chunk_count > 0:
        print(f"Chunks created: {chunk_count}")
    
    if passed == len(checks):
        print("\n🎉 All checks passed! Ready for Week 3.")
        return True
    else:
        print("\n⚠️  Some checks failed. Review and fix before continuing.")
        return False

if __name__ == "__main__":
    success = check_requirements()
    sys.exit(0 if success else 1)
```

Run checkpoint:
```bash
python scripts/checkpoint_week2.py
```

---

## SUCCESS CRITERIA FOR WEEK 2

✅ **Must Have:**
- [ ] Python environment with all dependencies
- [ ] 1-2 Cisco PDF documents downloaded
- [ ] 500+ chunks in ChromaDB
- [ ] Can retrieve commands for test queries
- [ ] Hierarchical tiering working (Tier 1, 2, 3)

⚠️ **Nice to Have:**
- [ ] 1000+ chunks (more is better)
- [ ] Multiple documents processed
- [ ] Comprehensive testing
- [ ] Detailed documentation

---

## COMMON ISSUES & SOLUTIONS

### Issue 1: PDF extraction fails
**Solution:** Try different PDF library
```python
# Alternative: Use pdfplumber
pip install pdfplumber

import pdfplumber
with pdfplumber.open(pdf_path) as pdf:
    text = pdf.pages[0].extract_text()
```

### Issue 2: ChromaDB errors
**Solution:** Delete and recreate
```bash
rm -rf data/chroma_db
python src/data_processing/pipeline.py
```

### Issue 3: Too few chunks
**Solution:** Adjust chunking parameters
```python
# In chunker.py, modify section detection
# Make sections smaller for more chunks
```

### Issue 4: Retrieval not working
**Solution:** Check embedding model
```python
# ChromaDB uses default embedding model
# If needed, specify explicitly:
from chromadb.utils import embedding_functions
ef = embedding_functions.DefaultEmbeddingFunction()
```

---

## NEXT STEPS (WEEK 3-4)

After completing Week 2:

1. **Intent Parser** (Week 3)
   - Build structured intent extraction
   - Map 10-15 intent types
   - Create test intents

2. **LLM Integration** (Week 3-4)
   - Groq API integration
   - Prompt engineering
   - Configuration generation

3. **Validation** (Week 4)
   - Batfish integration
   - Basic semantic checks

---

## DAILY LOG TEMPLATE

Track your progress:

```markdown
## Day X: Y Month 2026

### Completed:
- [Task 1]
- [Task 2]

### Issues:
- [Issue encountered]
- [How you solved it]

### Next:
- [Task for tomorrow]

### Time Spent: X hours
```

---

**Questions?** 
- Stuck on PDF extraction? → Try different library
- ChromaDB issues? → Delete and restart
- Not enough chunks? → Process more pages

**Remember**: 500+ chunks is the goal, but 300+ is acceptable for Week 2. You can always add more later!
