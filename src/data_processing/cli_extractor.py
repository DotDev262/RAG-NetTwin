"""
CLI-Focused Chunk Extractor
Extracts actual CLI commands from PDFs and creates focused chunks for RAG.
"""

import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Set
import hashlib

# Add parent to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data_processing.pdf_extractor import extract_text_from_pdf
from src.rag.vector_store import VectorStore


class CLIExtractor:
    """Extract CLI commands from documentation."""

    CISCO_PATTERNS = [
        # Interface config
        (
            r"(?:interface\s+(?:GigabitEthernet|FastEthernet|Serial|Ethernet|Vlan)\S+)",
            "interface",
        ),
        (r"(?:ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+)", "ip-address"),
        (r"(?:ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+)", "ip-address"),
        # OSPF
        (r"(?:router\s+ospf\s+\d+)", "router-ospf"),
        (
            r"(?:network\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+\s+area\s+\d+)",
            "ospf-network",
        ),
        (r"(?:area\s+\d+\.\d+\.\d+\.\d+)", "ospf-area"),
        # BGP
        (r"(?:router\s+bgp\s+\d+)", "router-bgp"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+remote-as\s+\d+)", "bgp-neighbor"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+peer-group)", "bgp-peer-group"),
        # ACL
        (r"(?:ip\s+access-list\s+(?:extended|standard)\s+\S+)", "acl-named"),
        (r"(?:access-list\s+\d+\s+(?:permit|deny))", "acl-numbered"),
        # Static route
        (r"(?:ip\s+route\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+)", "static-route"),
        # VLAN
        (r"(?:vlan\s+\d+)", "vlan"),
        (r"(?:switchport\s+mode\s+(?:trunk|access))", "switchport"),
        # Various
        (r"(?:hostname\s+\S+)", "hostname"),
        (r"(?:ntp\s+server\s+\d+\.\d+\.\d+\.\d+)", "ntp"),
        (r"(?:snmp-server\s+community\s+\S+)", "snmp"),
        (r"(?:logging\s+host\s+\d+\.\d+\.\d+\.\d+)", "logging"),
        (r"(?:username\s+\S+\s+privilege\s+\d+)", "aaa-user"),
        (r"(?:router\s+eigrp\s+\d+)", "router-eigrp"),
    ]

    JUNIPER_PATTERNS = [
        # Interface
        (r"(?:set\s+interfaces\s+\S+)", "interface"),
        (
            r"(?:set\s+interfaces\s+\S+\s+unit\s+\d+\s+family\s+inet\s+address)",
            "interface-ip",
        ),
        # OSPF
        (r"(?:set\s+protocols\s+ospf\s+area\s+\d+\.\d+\.\d+\.\d+)", "ospf-area"),
        (
            r"(?:set\s+protocols\s+ospf\s+area\s+\d+\.\d+\.\d+\.\d+\s+interface)",
            "ospf-interface",
        ),
        # BGP
        (r"(?:set\s+protocols\s+bgp\s+group\s+\S+)", "bgp-group"),
        (
            r"(?:set\s+protocols\s+bgp\s+group\s+\S+\s+neighbor\s+\d+\.\d+\.\d+\.\d+)",
            "bgp-neighbor",
        ),
        # Static route
        (
            r"(?:set\s+routing-options\s+static\s+route\s+\d+\.\d+\.\d+\.\d+/)",
            "static-route",
        ),
        # Firewall
        (r"(?:set\s+firewall\s+family\s+inet\s+filter\s+\S+)", "firewall-filter"),
        # VLAN
        (r"(?:set\s+vlans\s+\S+\s+vlan-id\s+\d+)", "vlan"),
        # System
        (r"(?:set\s+system\s+host-name\s+\S+)", "hostname"),
        (r"(?:set\s+system\s+ntp\s+server\s+\d+\.\d+\.\d+\.\d+)", "ntp"),
    ]

    def extract_from_text(self, text: str, vendor: str) -> List[Dict]:
        """Extract CLI commands from text."""
        chunks = []
        patterns = self.CISCO_PATTERNS if vendor == "cisco" else self.JUNIPER_PATTERNS

        for pattern, cmd_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Create a focused chunk with the command
                chunk_text = f"Command: {match}\nType: {cmd_type}\nVendor: {vendor}"
                chunk_id = hashlib.md5(f"{vendor}:{match}".encode()).hexdigest()[:16]

                chunks.append(
                    {
                        "id": f"{vendor}_{cmd_type}_{chunk_id}",
                        "text": chunk_text,
                        "vendor": vendor,
                        "os_version": "ios-xe-17.6"
                        if vendor == "cisco"
                        else "junos-21.4",
                        "command": match,
                        "command_type": cmd_type,
                        "tier": 1,
                    }
                )

        return chunks

    def process_pdf(self, pdf_path: str, vendor: str) -> List[Dict]:
        """Extract CLI from a PDF file."""
        print(f"Processing {Path(pdf_path).name}...")
        pages = extract_text_from_pdf(pdf_path)

        all_chunks = []
        for page in pages:
            chunks = self.extract_from_text(page["text"], vendor)
            all_chunks.extend(chunks)

        print(f"  Found {len(all_chunks)} CLI commands")
        return all_chunks


def reindex_cli_chunks():
    """Re-index vector store with CLI-focused chunks."""
    extractor = CLIExtractor()
    vector_store = VectorStore()

    # Clear existing collection - delete all IDs
    print("Clearing existing collection...")
    try:
        existing = vector_store.collection.get()
        if existing.get("ids"):
            vector_store.collection.delete(ids=existing["ids"])
    except Exception as e:
        print(f"  Note: {e}")

    all_chunks = []

    # Process Cisco PDFs
    cisco_pdfs = [
        "data/raw_docs/catalyst_9300_cmdref_17_6.pdf",
        "data/raw_docs/catalyst_9500_cmdref_17_6.pdf",
    ]

    for pdf in cisco_pdfs:
        if os.path.exists(pdf):
            chunks = extractor.process_pdf(pdf, "cisco")
            all_chunks.extend(chunks)

    # Process Juniper PDFs
    juniper_pdfs = [
        "data/raw_docs/junos-cli.pdf",
    ]

    for pdf in juniper_pdfs:
        if os.path.exists(pdf):
            chunks = extractor.process_pdf(pdf, "juniper")
            all_chunks.extend(chunks)

    # Deduplicate by command
    seen = set()
    unique_chunks = []
    for chunk in all_chunks:
        key = chunk["command"].lower()
        if key not in seen:
            seen.add(key)
            unique_chunks.append(chunk)

    print(f"\nTotal unique CLI commands: {len(unique_chunks)}")

    # Add to vector store
    if unique_chunks:
        texts = [c["text"] for c in unique_chunks]
        metadatas = [
            {
                "vendor": c["vendor"],
                "os_version": c["os_version"],
                "tier": c["tier"],
                "command_type": c["command_type"],
                "source": "cli_extractor",
            }
            for c in unique_chunks
        ]
        ids = [c["id"] for c in unique_chunks]

        vector_store.collection.add(ids=ids, documents=texts, metadatas=metadatas)
        print(f"Added {len(unique_chunks)} CLI chunks to vector store")

    # Print stats
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
    reindex_cli_chunks()
