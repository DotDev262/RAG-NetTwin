"""
Enhanced CLI-Focused Chunker
Extracts actual CLI command examples from documentation with context.
"""

import re
import sys
from pathlib import Path
from typing import List, Dict
import hashlib

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_processing.pdf_extractor import extract_text_from_pdf
from rag.vector_store import VectorStore


CISCO_CLI_PATTERNS = [
    # Interface patterns with IP
    (
        r"(?m)^interface\s+(?:GigabitEthernet|FastEthernet|Serial|Port-channel|Tunnel|Vlan)\S+.*?(?=^interface|\Z)",
        "interface",
    ),
    (
        r"(?m)^\s+ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+.*?(?=^\s+\w|\Z)",
        "ip-address",
    ),
    # OSPF patterns
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
    # VLAN
    (r"(?m)^vlan\s+\d+.*?(?=^vlan|\Z)", "vlan"),
    (r"(?m)^switchport\s+mode\s+(?:trunk|access).*?(?=^switchport|\Z)", "switchport"),
    # System
    (r"(?m)^hostname\s+\S+.*", "hostname"),
    (r"(?m)^ntp\s+server\s+\d+\.\d+\.\d+\.\d+.*", "ntp"),
    (r"(?m)^snmp-server\s+community\s+\S+.*", "snmp"),
    (r"(?m)^username\s+\S+\s+privilege\s+\d+.*", "aaa-user"),
    (r"(?m)^logging\s+(?:host\s+)?\d+\.\d+\.\d+\.\d+.*", "logging"),
]

JUNIPER_CLI_PATTERNS = [
    # Interface
    (r"(?m)^set\s+interfaces\s+\S+.*?(?=^set\s+interfaces|\Z)", "interface"),
    # OSPF
    (r"(?m)^set\s+protocols\s+ospf.*?(?=^set\s+protocols\s+ospf|\Z)", "ospf"),
    # BGP
    (r"(?m)^set\s+protocols\s+bgp.*?(?=^set\s+protocols\s+bgp|\Z)", "bgp"),
    # Static route
    (
        r"(?m)^set\s+routing-options\s+static\s+route.*?(?=^set\s+routing-options|\Z)",
        "static-route",
    ),
    # Firewall
    (
        r"(?m)^set\s+firewall\s+family\s+inet\s+filter.*?(?=^set\s+firewall|\Z)",
        "firewall",
    ),
    # VLAN
    (r"(?m)^set\s+vlans\s+\S+.*?(?=^set\s+vlans|\Z)", "vlan"),
    # System
    (r"(?m)^set\s+system\s+host-name\s+\S+.*", "hostname"),
    (r"(?m)^set\s+system\s+ntp\s+server\s+\d+\.\d+\.\d+\.\d+.*", "ntp"),
]


def extract_cli_examples(text: str, vendor: str) -> List[Dict]:
    """Extract CLI command examples from text."""
    chunks = []
    patterns = CISCO_CLI_PATTERNS if vendor == "cisco" else JUNIPER_CLI_PATTERNS

    for pattern, cmd_type in patterns:
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            # Clean up the match - take just the CLI part
            cli_text = match.strip()
            if len(cli_text) > 20 and len(cli_text) < 2000:  # Reasonable length
                chunk_id = hashlib.md5(
                    f"{vendor}:{cmd_type}:{cli_text[:50]}".encode()
                ).hexdigest()[:16]

                chunks.append(
                    {
                        "id": f"{vendor}_{cmd_type}_{chunk_id}",
                        "text": f"CLI Example ({vendor} {cmd_type}):\n{cli_text}",
                        "vendor": vendor,
                        "os_version": "ios-xe-17.6"
                        if vendor == "cisco"
                        else "junos-21.4",
                        "command_type": cmd_type,
                        "tier": 1,  # High priority CLI examples
                    }
                )

    return chunks


def process_file_with_cli_extraction(pdf_path: str, vendor: str) -> List[Dict]:
    """Process a PDF and extract CLI examples."""
    print(f"  Processing {Path(pdf_path).name}...")
    pages = extract_text_from_pdf(pdf_path)

    all_chunks = []

    # Extract CLI from each page
    for page in pages:
        chunks = extract_cli_examples(page["text"], vendor)
        all_chunks.extend(chunks)

    print(f"    Found {len(all_chunks)} CLI examples")
    return all_chunks


def reindex_with_cli_focus():
    """Re-index vector store with CLI-focused chunks."""
    vector_store = VectorStore()

    # Clear existing
    print("Clearing existing collection...")
    try:
        existing = vector_store.collection.get()
        if existing.get("ids"):
            vector_store.collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"  Note: {e}")

    all_chunks = []

    # Process Cisco PDFs - these have the most CLI examples
    cisco_pdfs = [
        "data/raw_docs/catalyst_9300_cmdref_17_6.pdf",
        "data/raw_docs/catalyst_9500_cmdref_17_6.pdf",
        "data/raw_docs/catalyst_9200_config_guide_17_6.pdf",
    ]

    for pdf in cisco_pdfs:
        if Path(pdf).exists():
            chunks = process_file_with_cli_extraction(pdf, "cisco")
            all_chunks.extend(chunks)

    # Process Juniper PDFs
    juniper_pdfs = [
        "data/raw_docs/junos-cli.pdf",
        "data/raw_docs/junos-ospf.pdf",
    ]

    for pdf in juniper_pdfs:
        if Path(pdf).exists():
            chunks = process_file_with_cli_extraction(pdf, "juniper")
            all_chunks.extend(chunks)

    # Deduplicate by content
    seen = set()
    unique_chunks = []
    for chunk in all_chunks:
        key = chunk["text"][:100].lower()
        if key not in seen:
            seen.add(key)
            unique_chunks.append(chunk)

    print(f"\nTotal unique CLI examples: {len(unique_chunks)}")

    # Add to vector store
    if unique_chunks:
        texts = [c["text"] for c in unique_chunks]
        metadatas = [
            {
                "vendor": c["vendor"],
                "os_version": c["os_version"],
                "tier": c["tier"],
                "command_type": c["command_type"],
                "source": "cli_focused",
            }
            for c in unique_chunks
        ]
        ids = [c["id"] for c in unique_chunks]

        vector_store.collection.add(ids=ids, documents=texts, metadatas=metadatas)
        print(f"Added {len(unique_chunks)} CLI-focused chunks")

    # Stats
    vendor_counts = {}
    type_counts = {}
    for chunk in unique_chunks:
        vendor_counts[chunk["vendor"]] = vendor_counts.get(chunk["vendor"], 0) + 1
        type_counts[chunk["command_type"]] = (
            type_counts.get(chunk["command_type"], 0) + 1
        )

    print(f"\nVendor distribution: {vendor_counts}")
    print(f"Command types: {type_counts}")


if __name__ == "__main__":
    reindex_with_cli_focus()
