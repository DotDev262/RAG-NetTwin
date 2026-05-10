"""
CLI-Focused Chunk Extractor for RAG-NetTwin.

This module extracts individual CLI commands from PDF documentation
and creates focused chunks for the vector database. Unlike the more
complex chunker, this focuses on individual command-level extraction
for precise retrieval.

Key Features:
- Regex-based CLI command extraction
- Vendor-specific patterns (Cisco IOS vs Juniper JunOS)
- Command type categorization
- Deduplication by command content

Typical Usage:
    from data_processing.cli_extractor import CLIExtractor

    extractor = CLIExtractor()
    chunks = extractor.process_pdf("data/raw_docs/cisco_cmdref.pdf", "cisco")
    print(f"Extracted {len(chunks)} CLI commands")
"""

import re
import os
from pathlib import Path
from typing import List, Dict
import hashlib

# Add parent to path for imports
project_root = Path(__file__).parent.parent.parent

from src.data_processing.pdf_extractor import extract_text_from_pdf  # noqa: E402
from src.rag.vector_store import VectorStore  # noqa: E402


class CLIExtractor:
    """
    Extracts CLI commands from documentation PDFs.

    This class uses regex patterns to identify network device CLI
    commands within documentation text. It categorizes commands by
    type (interface, router, ACL, etc.) and creates focused chunks
    suitable for RAG retrieval.

    Each extracted command is associated with a vendor (Cisco/Juniper)
    and assigned a default OS version. The tier is set to 1 (highest
    priority) for these focused CLI chunks.

    Attributes:
        CISCO_PATTERNS: List of (regex_pattern, command_type) tuples
            for Cisco IOS CLI commands.
        JUNIPER_PATTERNS: List of (regex_pattern, command_type) tuples
            for Juniper JunOS CLI commands.

    Example:
        >>> extractor = CLIExtractor()
        >>> chunks = extractor.extract_from_text(page_text, "cisco")
        >>> len(chunks)
        15
    """

    # Cisco IOS command patterns - matches common configuration commands
    # Each tuple contains: (regex_pattern, command_type)
    CISCO_PATTERNS = [
        # Interface config patterns
        (
            r"(?:interface\s+(?:GigabitEthernet|FastEthernet|Serial|Ethernet|Vlan|Port-channel|Loopback|Tunnel)\S+)",
            "interface",
        ),
        (r"(?:ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+)", "ip-address"),
        (r"(?:ip\s+address\s+\d+\.\d+\.\d+\.\d+\s+\d+)", "ip-address"),
        (r"(?:description\s+.*)", "description"),
        (r"(?:no\s+shutdown)", "no-shutdown"),
        (r"(?:mtu\s+\d+)", "mtu"),
        # OSPF patterns
        (r"(?:router\s+ospf\s+\d+)", "router-ospf"),
        (r"(?:router-id\s+\d+\.\d+\.\d+\.\d+)", "router-id"),
        (
            r"(?:network\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+\s+area\s+\d+)",
            "ospf-network",
        ),
        (r"(?:area\s+\d+\s+.*)", "ospf-area"),
        (r"(?:ip\s+ospf\s+\d+\s+area\s+\d+)", "ip-ospf-area"),
        (r"(?:ip\s+ospf\s+hello-interval\s+\d+)", "ospf-hello"),
        (r"(?:ip\s+ospf\s+dead-interval\s+\d+)", "ospf-dead"),
        (r"(?:ip\s+ospf\s+priority\s+\d+)", "ospf-priority"),
        # BGP patterns
        (r"(?:router\s+bgp\s+\d+)", "router-bgp"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+remote-as\s+\d+)", "bgp-neighbor"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+peer-group)", "bgp-peer-group"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+activate)", "bgp-activate"),
        (r"(?:neighbor\s+\d+\.\d+\.\d+\.\d+\s+next-hop-self)", "bgp-next-hop"),
        # ACL patterns
        (r"(?:ip\s+access-list\s+(?:extended|standard)\s+\S+)", "acl-named"),
        (r"(?:access-list\s+\d+\s+(?:permit|deny)\s+.*)", "acl-numbered"),
        # Static route
        (r"(?:ip\s+route\s+\d+\.\d+\.\d+\.\d+\s+\d+\.\d+\.\d+\.\d+\s+.*)", "static-route"),
        # VLAN patterns
        (r"(?:vlan\s+\d+)", "vlan"),
        (r"(?:name\s+\S+)", "vlan-name"),
        (r"(?:switchport\s+mode\s+(?:trunk|access))", "switchport"),
        (r"(?:switchport\s+access\s+vlan\s+\d+)", "switchport-vlan"),
        # System patterns
        (r"(?:hostname\s+\S+)", "hostname"),
        (r"(?:ntp\s+server\s+\d+\.\d+\.\d+\.\d+)", "ntp"),
        (r"(?:snmp-server\s+community\s+\S+)", "snmp"),
        (r"(?:logging\s+host\s+\d+\.\d+\.\d+\.\d+)", "logging"),
        (r"(?:username\s+\S+\s+privilege\s+\d+\s+password\s+\S+)", "aaa-user"),
        # Routing
        (r"(?:router\s+eigrp\s+\d+)", "router-eigrp"),
    ]

    # Juniper JunOS command patterns - uses "set" command syntax
    JUNIPER_PATTERNS = [
        # Interface patterns
        (r"(?:set\s+interfaces\s+\S+)", "interface"),
        (
            r"(?:set\s+interfaces\s+\S+\s+unit\s+\d+\s+family\s+inet\s+address\s+\d+\.\d+\.\d+\.\d+/\d+)",
            "interface-ip",
        ),
        (r"(?:set\s+interfaces\s+\S+\s+description\s+.*)", "description"),
        # OSPF patterns
        (r"(?:set\s+protocols\s+ospf\s+area\s+\d+\.\d+\.\d+\.\d+)", "ospf-area"),
        (
            r"(?:set\s+protocols\s+ospf\s+area\s+\d+\.\d+\.\d+\.\d+\s+interface\s+\S+)",
            "ospf-interface",
        ),
        (
            r"(?:set\s+protocols\s+ospf\s+area\s+\d+\.\d+\.\d+\.\d+\s+interface\s+\S+\s+hello-interval\s+\d+)",
            "ospf-hello",
        ),
        # BGP patterns
        (r"(?:set\s+protocols\s+bgp\s+group\s+\S+)", "bgp-group"),
        (
            r"(?:set\s+protocols\s+bgp\s+group\s+\S+\s+neighbor\s+\d+\.\d+\.\d+\.\d+)",
            "bgp-neighbor",
        ),
        (
            r"(?:set\s+protocols\s+bgp\s+group\s+\S+\s+peer-as\s+\d+)",
            "bgp-peer-as",
        ),
        # Static route
        (
            r"(?:set\s+routing-options\s+static\s+route\s+\d+\.\d+\.\d+\.\d+/\d+\s+next-hop\s+\d+\.\d+\.\d+\.\d+)",
            "static-route",
        ),
        (
            r"(?:set\s+routing-options\s+autonomous-system\s+\d+)",
            "bgp-as",
        ),
        # Firewall filter
        (r"(?:set\s+firewall\s+family\s+inet\s+filter\s+\S+)", "firewall-filter"),
        # VLAN
        (r"(?:set\s+vlans\s+\S+\s+vlan-id\s+\d+)", "vlan"),
        # System
        (r"(?:set\s+system\s+host-name\s+\S+)", "hostname"),
        (r"(?:set\s+system\s+ntp\s+server\s+\d+\.\d+\.\d+\.\d+)", "ntp"),
    ]

    def extract_from_text(self, text: str, vendor: str) -> List[Dict]:
        """
        Extract CLI commands from plain text.

        This method scans the input text for matches against vendor-specific
        regex patterns and creates chunks for each matched command.

        Args:
            text: Plain text extracted from documentation.
            vendor: Vendor identifier ("cisco" or "juniper").

        Returns:
            List of chunk dictionaries, each containing:
                - id: Unique chunk identifier
                - text: Formatted command text with type and vendor
                - vendor: Vendor name
                - os_version: Default OS version for the vendor
                - command: The extracted command string
                - command_type: Categorized type (e.g., "interface", "ospf")
                - tier: Priority level (1 = highest)
        """
        chunks = []
        # Select appropriate pattern set based on vendor
        patterns = self.CISCO_PATTERNS if vendor == "cisco" else self.JUNIPER_PATTERNS

        # Iterate through patterns and find matches
        for pattern, cmd_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Create a focused chunk with the command
                chunk_text = f"Command: {match}\nType: {cmd_type}\nVendor: {vendor}"
                # Generate unique ID from vendor and command
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
        """
        Extract CLI commands from a PDF file.

        This method reads a PDF, extracts text from each page, and applies
        command extraction to the text.

        Args:
            pdf_path: Path to the PDF file.
            vendor: Vendor identifier ("cisco" or "juniper").

        Returns:
            List of extracted command chunks from all pages.
        """
        print(f"Processing {Path(pdf_path).name}...")
        pages = extract_text_from_pdf(pdf_path)

        all_chunks = []
        # Process each page separately
        for page in pages:
            chunks = self.extract_from_text(page["text"], vendor)
            all_chunks.extend(chunks)

        print(f"  Found {len(all_chunks)} CLI commands")
        return all_chunks


def reindex_cli_chunks():
    """
    Re-index the vector store with CLI-focused chunks.

    This is a standalone function that processes documentation PDFs
    and populates the vector store with CLI command chunks. It:
    1. Clears the existing collection
    2. Processes Cisco and Juniper PDFs
    3. Deduplicates commands by content
    4. Adds unique chunks to the vector store

    Note:
        This function expects PDF files to exist at the specified paths.
        Adjust the paths as needed for your documentation set.
    """
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
        "data/raw_docs/cisco_routing_17_15.pdf",
        "data/raw_docs/catalyst_9300_config_guide_17_6.pdf"
    ]

    for pdf in cisco_pdfs:
        if os.path.exists(pdf):
            chunks = extractor.process_pdf(pdf, "cisco")
            all_chunks.extend(chunks)

    # Process Juniper PDFs
    juniper_pdfs = [
        "data/raw_docs/junos-cli.pdf",
        "data/raw_docs/junos-ospf.pdf",
        "data/raw_docs/junos_bgp_config.pdf",
        "data/raw_docs/junos_routing_policy.pdf",
        "data/raw_docs/junos_ethernet_switching.pdf"
    ]

    for pdf in juniper_pdfs:
        if os.path.exists(pdf):
            chunks = extractor.process_pdf(pdf, "juniper")
            all_chunks.extend(chunks)

    # Deduplicate by command content
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

    # Print statistics
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
