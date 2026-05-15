"""
Enhanced CLI-Focused Chunker for RAG-NetTwin.

This module extracts CLI command examples with surrounding context from
PDF documentation. Unlike the simpler CLIExtractor, this captures
multi-line command blocks and their context for richer retrieval.

Key Features:
- Multi-line CLI block extraction with context
- Vendor-specific pattern matching
- Command type categorization
- Context-aware chunking (preserves related commands together)

Typical Usage:
    from data_processing.cli_chunker import process_file_with_cli_extraction

    chunks = process_file_with_cli_extraction("data/raw_docs/cisco_guide.pdf", "cisco")
    print(f"Extracted {len(chunks)} CLI examples with context")
"""

import re
import json
from pathlib import Path
from typing import List, Dict
import hashlib

# Add project root to path for imports

from src.data_processing.pdf_extractor import extract_text_from_pdf
from src.rag.vector_store import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Cisco IOS CLI patterns - captures command blocks with context
# Each tuple: (regex_pattern, command_category)
CISCO_CLI_PATTERNS = [
    # Interface patterns with IP configuration
    (
        r"(?m)^interface\s+(?:GigabitEthernet|FastEthernet|Serial|Port-channel|Tunnel|Vlan)\S+.*?(?=^interface|\Z)",
        "interface",
    ),
    (
        r"(?m)^\s+ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+.*?(?=^\s+\w|\Z)",
        "ip-address",
    ),
    # OSPF patterns - captures router config and network statements
    (r"(?m)^router\s+ospf\s+\d+.*?(?=^router|\Z)", "router-ospf"),
    (
        r"(?m)^\s+network\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+\s+area\s+\d+.*?(?=^\s+\w|\Z)",
        "ospf-network",
    ),
    (r"(?m)^\s+area\s+\d+\.\d+\.\d+\.\d+.*?(?=^\s+\w|\Z)", "ospf-area"),
    # BGP patterns
    (r"(?m)^router\s+bgp\s+\d+.*?(?=^router|\Z)", "router-bgp"),
    (
        r"(?m)^\s+neighbor\s+\d+\.\d+\.\d+\.\d+\s+(?:remote-as|peer-group).*?(?=^\s+\w|\Z)",
        "bgp-neighbor",
    ),
    # ACL patterns
    (
        r"(?m)^ip\s+access-list\s+(?:extended|standard)\s+\S+.*?(?=^ip\s+access-list|\Z)",
        "acl-named",
    ),
    (r"(?m)^access-list\s+\d+\s+(?:permit|deny).*?(?=^access-list|\Z)", "acl-numbered"),
    # Static route
    (
        r"(?m)^ip\s+route\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+.*?(?=^ip\s+route|\Z)",
        "static-route",
    ),
    # NetFlow (Flexible NetFlow) patterns
    (
        r"(?m)^flow\s+(?:record|monitor|exporter)\s+\S+.*?(?=^flow|\Z)",
        "netflow",
    ),
    # VLAN patterns
    (r"(?m)^vlan\s+\d+.*?(?=^vlan|\Z)", "vlan"),
    (r"(?m)^switchport\s+mode\s+(?:trunk|access).*?(?=^switchport|\Z)", "switchport"),
    # System patterns
    (r"(?m)^hostname\s+\S+.*", "hostname"),
    (r"(?m)^ntp\s+server\s+\d+\.\d+\.\d+\.\d+.*", "ntp"),
    (r"(?m)^snmp-server\s+community\s+\S+.*", "snmp"),
    (r"(?m)^username\s+\S+\s+privilege\s+\d+.*", "aaa-user"),
    (r"(?m)^logging\s+(?:host\s+)?\d+\.\d+\.\d+\.\d+.*", "logging"),
]

# Juniper JunOS CLI patterns - uses "set" command syntax
JUNIPER_CLI_PATTERNS = [
    # Interface configuration
    (r"(?m)^set\s+interfaces\s+\S+.*?(?=^set\s+interfaces|\Z)", "interface"),
    # OSPF protocol configuration
    (r"(?m)^set\s+protocols\s+ospf.*?(?=^set\s+protocols\s+ospf|\Z)", "ospf"),
    # BGP protocol configuration
    (r"(?m)^set\s+protocols\s+bgp.*?(?=^set\s+protocols\s+bgp|\Z)", "bgp"),
    # Static route configuration
    (
        r"(?m)^set\s+routing-options\s+static\s+route.*?(?=^set\s+routing-options|\Z)",
        "static-route",
    ),
    # Firewall filter configuration
    (
        r"(?m)^set\s+firewall\s+family\s+inet\s+filter.*?(?=^set\s+firewall|\Z)",
        "firewall",
    ),
    # VLAN configuration
    (r"(?m)^set\s+vlans\s+\S+.*?(?=^set\s+vlans|\Z)", "vlan"),
    # System configuration
    (r"(?m)^set\s+system\s+host-name\s+\S+.*", "hostname"),
    (r"(?m)^set\s+system\s+ntp\s+server\s+\d+\.\d+\.\d+\.\d+.*", "ntp"),
]


def extract_cli_examples(
    text: str, vendor: str, source_file: str = "unknown", page_num: int = 0
) -> List[Dict]:
    """
    Extract CLI command examples with context from text.

    This function uses multi-line regex patterns to capture command
    blocks including their sub-commands and parameters. It filters
    out too-short or too-long matches to ensure quality chunks.

    Args:
        text: Documentation text to scan for CLI examples.
        vendor: Vendor identifier ("cisco" or "juniper").
        source_file: Source PDF filename for provenance tracking.
        page_num: Page number in the source PDF.

    Returns:
        List of chunk dictionaries, each containing:
            - id: Unique identifier
            - text: Formatted CLI example with vendor and type
            - vendor: Vendor name
            - os_version: Default OS version for vendor
            - command_type: Command category
            - source_file: Source PDF filename
            - page_range: [page_num, page_num] for provenance
            - context_tags: List of topic tags
            - command_hierarchy: Empty (CLI top-level)
            - tier: Priority level (1 = highest)
    """
    chunks = []
    patterns = CISCO_CLI_PATTERNS if vendor == "cisco" else JUNIPER_CLI_PATTERNS

    for pattern, cmd_type in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            # Clean up the match - take just the CLI part
            cli_text = match.strip()
            # Filter by reasonable length (20-2000 chars)
            # Too short = likely partial match, too long = full config
            if len(cli_text) > 20 and len(cli_text) < 2000:
                chunk_id = hashlib.md5(cli_text.encode()).hexdigest()[:16]

                chunks.append(
                    {
                        "id": f"{vendor}_{cmd_type}_{chunk_id}",
                        "text": f"CLI Example ({vendor} {cmd_type}):\n{cli_text}",
                        "vendor": vendor,
                        "os_version": "ios-xe-17.6"
                        if vendor == "cisco"
                        else "junos-21.4",
                        "command_type": cmd_type,
                        "source_file": source_file,
                        "page_range": [page_num, page_num],
                        "context_tags": [cmd_type, vendor, "cli"],
                        "command_hierarchy": [],
                        "tier": 1,
                    }
                )

    return chunks


BOILERPLATE_KEYWORDS = [
    "copyright",
    "all rights reserved",
    "table of contents",
    "preface",
    "intended audience",
    "document history",
    "legal notice",
    "trademark",
    "proprietary information",
]


def extract_semantic_chunks(
    text: str,
    vendor: str,
    tier: int = 2,
    source_file: str = "unknown",
    page_num: int = 0,
) -> List[Dict]:
    """
    Extracts high-level semantic chunks (Recommendation 1).
    Tier 2: Semantic Paragraphs (~500 chars)
    Tier 3: Full Sections (~1500 chars)
    """
    if tier == 2:
        chunk_size = 500
        overlap = 50
    else:
        chunk_size = 1500
        overlap = 150

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    docs = splitter.split_text(text)
    chunks = []

    min_length = 40 if tier == 1 else 150

    for i, doc_text in enumerate(docs):
        text_lower = doc_text.lower()

        # Filter very short chunks
        if len(doc_text) < min_length:
            continue

        # Filter boilerplate (copyright, legal, etc.)
        if any(kw in text_lower for kw in BOILERPLATE_KEYWORDS):
            continue

        content_hash = hashlib.md5(doc_text.encode()).hexdigest()[:12]

        chunks.append(
            {
                "id": f"{vendor}_tier{tier}_{content_hash}",
                "text": f"Tier {tier} Context ({vendor}):\n{doc_text}",
                "vendor": vendor,
                "os_version": "ios-xe-17.6" if vendor == "cisco" else "junos-21.4",
                "command_type": "conceptual",
                "source_file": source_file,
                "page_range": [page_num, page_num],
                "context_tags": [vendor, f"tier{tier}"],
                "command_hierarchy": [],
                "tier": tier,
            }
        )

    return chunks


def process_file_with_cli_extraction(pdf_path: str, vendor: str) -> List[Dict]:
    """
    Process a PDF and extract CLI examples with context.

    This function reads a PDF, extracts text from all pages, and
    applies CLI extraction to each page.

    Args:
        pdf_path: Path to the PDF file.
        vendor: Vendor identifier ("cisco" or "juniper").

    Returns:
        List of extracted CLI example chunks from all pages.
    """
    source_file = Path(pdf_path).name
    print(f"  Processing {source_file}...")
    pages = extract_text_from_pdf(pdf_path, use_hybrid=False)

    all_chunks = []

    # Extract CLI from each page
    for page_idx, page in enumerate(pages):
        page_num = page.get("page_num", page_idx + 1)

        # Step 1: Create the "Parent" chunk for this page (Tier 2)
        # This provides the conceptual anchor for all CLI blocks on the same page
        tier2_parents = extract_semantic_chunks(
            page["text"], vendor, tier=2, source_file=source_file, page_num=page_num
        )
        all_chunks.extend(tier2_parents)

        # We pick the first Tier 2 chunk as the primary parent for this page
        parent_id = tier2_parents[0]["id"] if tier2_parents else None

        # Step 2: Tier 1: Precise CLI blocks (linked to Parent)
        tier1 = extract_cli_examples(
            page["text"], vendor, source_file=source_file, page_num=page_num
        )
        if parent_id:
            for c in tier1:
                c["parent_id"] = parent_id  # Critical link for Recommendation Elite
        all_chunks.extend(tier1)

        # Step 3: Tier 3: Broad sections
        tier3 = extract_semantic_chunks(
            page["text"], vendor, tier=3, source_file=source_file, page_num=page_num
        )
        all_chunks.extend(tier3)

    print(f"    Found {len(all_chunks)} chunks across linked hierarchy")
    return all_chunks


def reindex_with_cli_focus(json_only: bool = False):
    """
    Re-index the vector store by automatically discovering all PDFs in raw_docs.

    Args:
        json_only: If True, export clean chunks to JSON and skip ChromaDB indexing.
    """
    if not json_only:
        vector_store = VectorStore()
        # Clear existing collection
        print("Clearing existing collection...")
        try:
            existing = vector_store.collection.get()
            if existing.get("ids"):
                ids = existing["ids"]
                for i in range(0, len(ids), 5000):
                    vector_store.collection.delete(ids=ids[i : i + 5000])
        except Exception as e:
            print(f"  Note: {e}")

    all_chunks = []
    raw_dir = Path("data/raw_docs")
    pdf_files = list(raw_dir.glob("*.pdf"))

    print(f"📁 Found {len(pdf_files)} PDFs in {raw_dir}")

    for pdf in pdf_files:
        filename = pdf.name.lower()

        # Vendor detection logic
        if any(
            k in filename
            for k in ["cisco", "catalyst", "ios", "xe", "nexus", "programmability"]
        ):
            vendor = "cisco"
        elif any(
            k in filename
            for k in ["junos", "juniper", "junoos", "mx", "ex", "srx", "qfx"]
        ):
            vendor = "juniper"
        else:
            # Skip unknown vendors to maintain research quality
            print(f"  ⏩ Skipping {pdf.name} (unknown vendor)")
            continue

        chunks = process_file_with_cli_extraction(str(pdf), vendor)
        all_chunks.extend(chunks)

    # Quality gate: filter too-short and boilerplate chunks
    initial_count = len(all_chunks)
    filtered_chunks = []
    for chunk in all_chunks:
        text = chunk.get("text", "").lower()
        tier = chunk.get("tier", 2)
        if tier == 1:
            if len(text) > 40:
                filtered_chunks.append(chunk)
            continue
        if len(text) < 150:
            continue
        if any(kw in text for kw in BOILERPLATE_KEYWORDS):
            continue
        filtered_chunks.append(chunk)

    removed_count = initial_count - len(filtered_chunks)
    print(
        f"Quality gate: removed {removed_count} noise chunks, kept {len(filtered_chunks)}"
    )

    # Deduplicate by full text content (catches cross-file duplicates)
    seen_texts = {}
    for chunk in filtered_chunks:
        text_key = chunk.get("text", "")
        if text_key not in seen_texts:
            seen_texts[text_key] = chunk
    unique_chunks = list(seen_texts.values())
    dup_count = len(filtered_chunks) - len(unique_chunks)
    if dup_count:
        print(f"Dedup: removed {dup_count} duplicate texts")

    print(f"\nTotal chunks: {len(unique_chunks)}")

    if json_only:
        out_dir = Path("data/processed_chunks")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "all_chunks.json"
        with open(out_path, "w") as f:
            json.dump(unique_chunks, f, indent=2)
        print(f"Exported {len(unique_chunks)} chunks to {out_path}")
    else:
        if unique_chunks:
            vector_store.add_chunks(unique_chunks)
            print(
                f"Successfully added {len(unique_chunks)} total chunks across all tiers."
            )

    # Print statistics
    vendor_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for chunk in unique_chunks:
        vendor_counts[chunk["vendor"]] = vendor_counts.get(chunk["vendor"], 0) + 1
        type_counts[chunk["command_type"]] = (
            type_counts.get(chunk["command_type"], 0) + 1
        )

    print(f"\nVendor distribution: {vendor_counts}")
    print(f"Command types: {type_counts}")


if __name__ == "__main__":
    import sys

    json_only = "--json-only" in sys.argv
    reindex_with_cli_focus(json_only=json_only)
