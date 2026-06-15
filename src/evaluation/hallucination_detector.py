"""
Hallucination Detection Module for RAG-NetTwin.

This module detects common LLM hallucinations in generated network
configurations by identifying placeholder patterns and invalid citations.
It is a critical component of the "Grounding Audit Trail" system.

Key Features:
- Placeholder pattern detection (<YOUR_PASSWORD>, <ENTER_IP>, etc.)
- Citation validation against retrieved sources
- Regex-based pattern matching for efficiency
- Config cleaning to avoid false positives from citation comments

Typical Usage:
    from src.evaluation.hallucination_detector import HallucinationDetector

    detector = HallucinationDetector()
    report = detector.detect(
        config="interface Gig0/1\n ip address <YOUR_IP> 255.255.255.0",
        citations=["src_001", "src_002"],
        valid_source_ids=["src_001", "src_003"]
    )
    print(report.is_hallucinated)  # True
    print(report.suspicious_commands)  # ['<YOUR_IP>']
"""

import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from src.utils import setup_logger

logger = setup_logger("HallucinationDetector")


class HallucinationReport(BaseModel):
    """
    Pydantic model for hallucination detection results.

    Contains the detection outcome and detailed information about
    any suspicious elements found in the configuration.

    Attributes:
        is_hallucinated: Boolean indicating if hallucinations were detected.
        reason: Human-readable explanation of why detection failed.
        suspicious_commands: List of detected placeholder patterns.
        invalid_citations: List of citation IDs that don't match retrieved sources.
        ungrounded_commands: List of commands not found in retrieved documentation.
    """

    is_hallucinated: bool
    reason: Optional[str] = None
    suspicious_commands: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)
    ungrounded_commands: List[str] = Field(default_factory=list)
    unauthorized_parameters: List[str] = Field(
        description="Parameters (IPs, ASNs, VLANs) found in config but not in intent/plan",
        default_factory=list,
    )


class HallucinationDetector:
    """
    Detects common LLM hallucinations in network configurations.

    This detector identifies three types of hallucinations:
    1. Placeholder Hallucinations: LLM uses placeholder values (<YOUR_IP>).
    2. Citation Hallucinations: LLM cites sources that weren't retrieved.
    3. Grounding Hallucinations: LLM generates commands not present in docs.
    """

    # ... existing patterns ...
    HALLUCINATION_PATTERNS = [
        r"<YOUR_[A-Z_]+>",
        r"<ENTER_[A-Z_]+>",
        r"<SAMPLE_[A-Z_]+>",
        r"<EXAMPLE_[A-Z_]+>",
        r"<CHANGE_ME>",
        r"<REPLACE_[A-Z_]+>",
        r"ENTER_IP_HERE",
        r"YOUR_AS_NUMBER",
        r"command-not-found",
        r"PLACEHOLDER",
        r"dummy-config",
        r"\bUnknown\b",
        r"\bTBD\b",
        r"\bTBA\b",
        r"INSERT_.*_HERE",
    ]

    def detect(
        self,
        config: str,
        citations: List[str],
        valid_source_ids: List[str],
        retrieved_texts: Optional[List[str]] = None,
        intent_context: str = "",
        intent_params: Optional[Dict[str, Any]] = None,
        master_plan: Optional[Dict[str, Any]] = None,
        authorized_citations: Optional[List[str]] = None,
    ) -> HallucinationReport:
        """
        Detect hallucinations in a generated configuration.
        """
        suspicious = []
        invalid_cites = []
        ungrounded = []
        unauthorized = []

        # Authorized list includes provided IDs and general authorized names (guide titles)
        full_authorized = set(valid_source_ids + (authorized_citations or []))
        # Add global safe sources
        full_authorized.add("BASE_CLI_KNOWLEDGE")

        # Step 1: Remove citation references from config
        config_clean = re.sub(r"\[Ref: [^\]]+\]", "", config)

        # Step 2: Check for placeholder patterns
        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, config_clean)
            if matches:
                suspicious.extend(list(set(matches)))

        # Step 3: Check citation validity strictly against retrieved session chunk IDs
        for cite in citations:
            # Clean 'ID: ' prefix if LLM included it
            clean_cite = cite.replace("ID:", "").replace("id:", "").strip()
            clean_cite_lower = clean_cite.lower()

            found_valid = False

            # 1. Exact match first (most robust) - case-insensitive
            for auth in full_authorized:
                if auth.lower() == clean_cite_lower:
                    found_valid = True
                    break

            if not found_valid and cite:
                if len(clean_cite) > 0:
                    invalid_cites.append(cite)

        # Step 4: Command Grounding Check (Recommendation 2)
        if retrieved_texts or intent_context:
            all_docs = retrieved_texts or []
            ungrounded = self._check_command_grounding(
                config_clean, all_docs, intent_context
            )

        # Step 5: Parameter Binding Check (Recommendation 3)
        if intent_params or master_plan or retrieved_texts:
            unauthorized = self._check_parameter_binding(
                config_clean,
                intent_params or {},
                master_plan or {},
                grounding_context=retrieved_texts,
            )

        # Determine overall hallucination status
        is_hallucinated = (
            len(suspicious) > 0
            or len(invalid_cites) > 0
            or len(ungrounded) > 0
            or len(unauthorized) > 0
        )

        # Build reason string
        reason = None
        if is_hallucinated:
            reasons = []
            if suspicious:
                reasons.append(f"Placeholders found: {suspicious}")
            if invalid_cites:
                reasons.append(f"Invalid citations: {invalid_cites}")
            if ungrounded:
                reasons.append(f"Ungrounded commands: {ungrounded}")
            if unauthorized:
                reasons.append(f"Unauthorized parameters: {unauthorized}")
            reason = "; ".join(reasons)

        return HallucinationReport(
            is_hallucinated=is_hallucinated,
            reason=reason,
            suspicious_commands=suspicious,
            invalid_citations=invalid_cites,
            ungrounded_commands=ungrounded,
            unauthorized_parameters=unauthorized,
        )

    def _check_parameter_binding(
        self,
        config: str,
        intent_params: Dict[str, Any],
        master_plan: Dict[str, Any],
        grounding_context: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Verifies that all numeric identifiers in the config were authorized.
        Targets 'Invented Parameters' hallucination.
        """
        unauthorized = []

        # 1. Collect all authorized values from intent and plan
        authorized_values = set()

        # Add all tokens from grounding context to authorized values
        if grounding_context:
            for doc in grounding_context:
                # Extract words AND standalone numbers (including those with commas/dots)
                # This ensures 16,384 in docs authorizes 16384 in config
                tokens = re.findall(r"\b[\w\.\,]+\b", doc.lower())
                for t in tokens:
                    clean_t = t.replace(",", "").replace(" ", "").strip()
                    authorized_values.add(clean_t)
                    # Also add the original token if different
                    if clean_t != t:
                        authorized_values.add(t)

        def collect_values(d):
            if isinstance(d, dict):
                for v in d.values():
                    collect_values(v)
            elif isinstance(d, list):
                for v in d:
                    collect_values(v)
            elif d:
                # Store normalized string representation
                val_str = str(d).lower().strip()
                # If it's a CIDR, authorize the IP, the Network, and the Broadcast (Recommendation 5)
                if "/" in val_str and "." in val_str:
                    try:
                        import ipaddress

                        # strict=False allows passing a host address like 10.1.1.1/24
                        net = ipaddress.ip_network(val_str, strict=False)
                        authorized_values.add(str(net.network_address))
                        authorized_values.add(str(net.broadcast_address))
                        # Also add common "base" addresses if it's a large subnet
                        # e.g. for 172.16.0.0/16, add 172.16.0.0
                        authorized_values.add(val_str.split("/")[0])

                        # Add netmask
                        if net.netmask:
                            authorized_values.add(str(net.netmask))
                            # Invert mask: 255.255.255.0 -> 0.0.0.255
                            wildcard = ".".join(
                                [
                                    str(255 - int(octet))
                                    for int_octet in str(net.netmask).split(".")
                                    for octet in [int_octet]
                                ]
                            )
                            authorized_values.add(wildcard)
                    except (ValueError, Exception):
                        authorized_values.add(val_str.split("/")[0])
                authorized_values.add(val_str)
                # Add common interface name variations (e.g. Gig0/1 -> GigabitEthernet0/1)
                if "gig" in val_str:
                    authorized_values.add(
                        "gigabitethernet" + val_str.replace("gig", "")
                    )
                elif "ge-" in val_str:
                    authorized_values.add("ge-0/0/0")  # common default

        collect_values(intent_params)
        collect_values(master_plan)

        # 2. Extract potential identifiers from config
        # IP Addresses - ALWAYS check these strictly
        ips = re.findall(r"(\d+\.\d+\.\d+\.\d+)", config)

        # Numbers (ASNs, VLANs, Areas)
        # Only extract 4+ digit numbers as "potentially high-risk" (ASNs, large IDs)
        # or numbers that are explicitly NOT common network defaults/metrics.
        # We use a negative lookahead/lookbehind for colons to avoid picking up IPv6 segments.
        all_numbers = re.findall(r"(?<![.\w:])(\d+)(?![.\w:])", config)

        # Common safe values (standard defaults, common timers, MTUs, ports, costs, wildcard masks)
        SAFE_COMMON_VALUES = {
            # Interfaces & VLANs (Small common ones)
            "0",
            "1",
            "10",
            "100",
            "1000",
            # IP Components & Wildcard Masks (Recommendation: add common masks)
            "255.255.255.0",
            "255.255.255.255",
            "255.255.255.128",
            "255.255.255.192",
            "255.255.255.224",
            "255.255.255.240",
            "255.255.255.248",
            "255.255.255.252",
            "255.255.254.0",
            "255.255.252.0",
            "255.255.248.0",
            "255.255.240.0",
            "255.255.224.0",
            "255.255.192.0",
            "255.255.128.0",
            "255.255.0.0",
            "255.240.0.0",
            "255.0.0.0",
            "0.0.0.0",
            "0.0.0.3",
            "0.0.0.7",
            "0.0.0.15",
            "0.0.0.31",
            "0.0.0.63",
            "0.0.0.127",
            "0.0.0.255",
            "0.0.255.255",
            "0.255.255.255",
            "any",
            "log",
            # Common Base IPs (Defaults)
            "10.0.0.1",
            "192.168.1.1",
            "192.168.1.2",
            "10.1.1.1",
            "10.1.1.254",
            "172.16.1.1",
            "1.1.1.1",
            "2.2.2.2",
            "8.8.8.8",
            "8.8.4.4",
            # Common ASNs
            "65000",
            "65001",
            "65002",
            "65535",
            "64512",
            # CLI Keywords that are safe
            "permit",
            "deny",
            "sequence",
            "overload",
            "outside",
            "inside",
            "static",
            "dynamic",
            "description",
            "hostname",
            "interface",
            "router",
            "area",
            "network",
            "neighbor",
            "remote-as",
            "address-family",
            "activate",
            "exit-address-family",
            "exit",
            "unit",
            "family",
            "inet",
            "address",
            "vrrp-group",
            "virtual-address",
            "priority",
            "preempt",
            "track",
            "vlan-id",
            "vlan",
            "mode",
            "access",
            "trunk",
            "logging",
            "buffer-size",
            "exporter",
            "monitor",
            "record",
            "class-map",
            "policy-map",
            "service-policy",
            "match-any",
            "match-all",
            "cs6",
            "ef",
            "af11",
            "af21",
            "af31",
            "af41",
            "set",
            "interfaces",
            "ethernet",
            "protocols",
            "hello-interval",
            "ospf",
            "area",
            # MTU
            "1500",
            "9000",
            "9216",
            # Common Timers (seconds/minutes)
            "1",
            "3",
            "5",
            "10",
            "15",
            "30",
            "40",
            "60",
            "120",
            "180",
            "300",
            "600",
            # Ports
            "22",
            "23",
            "80",
            "443",
            "179",
            "161",
            "162",
            "500",
            "4500",
            # Metrics / Admin Dist
            "20",
            "110",
            "170",
            "200",
            "254",
            "1",
            "100",
            # Common memory/buffer sizes (Powers of 2)
            "1024",
            "2048",
            "4096",
            "8192",
            "16384",
            "32768",
            "65536",
            "131072",
            # Common intervals/counts
            "2",
            "4",
            "8",
            "16",
            "32",
            "64",
            "128",
            "256",
            "512",
        }

        for val in set(ips + all_numbers):
            # Skip if explicitly authorized or in the safe common set
            if val in authorized_values or val in SAFE_COMMON_VALUES:
                continue

            # Heuristic: Allow small numbers (1-1024) as they are often
            # common costs, timers, or well-known ports not in our safe set.
            # This significantly reduces false positives for OSPF costs, etc.
            if val.isdigit() and int(val) <= 1024:
                continue

            # Check if it's a substring of an authorized CIDR (e.g. 10.1.1.1 in 10.1.1.0/24)
            is_authorized = False
            for auth in authorized_values:
                if val in auth:
                    is_authorized = True
                    break

            if not is_authorized:
                unauthorized.append(val)

        return unauthorized

    def _check_command_grounding(
        self, config: str, docs: List[str], intent_context: str = ""
    ) -> List[str]:
        """
        Robust grounding check: verifies if config tokens are present in documentation
        OR derived from the user's intent. Prevents false positives on hostnames,
        IPs, and user-defined identifiers.
        """
        ungrounded = []
        full_doc_text = "\n".join(docs).lower()
        intent_norm = (intent_context or "").lower()

        # Noisy tokens that are common parts of commands but not informative for grounding
        NOISY = [
            "no",
            "set",
            "exit",
            "end",
            "quit",
            "commit",
            "logging",
            "snmp",
            "line",
            "vty",
            "banner",
            "enable",
            "configure",
            "terminal",
            "firewall",
            "filter",
            "term",
            "protocols",
            "interfaces",
            "system",
        ]

        # Verbs that are very common and often grounded by system knowledge
        COMMON_VERBS = [
            "interface",
            "router",
            "ip",
            "ipv6",
            "vlan",
            "access-list",
            "set",
            "show",
            "crypto",
            "policy",
            "tunnel",
            "route",
            "address",
            "ospf",
            "bgp",
            "switchport",
            "neighbor",
            "activate",
            "address-family",
            "unicast",
            "multicast",
            "snmp-server",
            "username",
            "hostname",
            "description",
            "logging",
            "system",
            "remote-as",
            "area",
            "permit",
            "port-channel",
            "port-channels",
            "etherchannel",
            "etherchannels",
            "lacp",
            "qos",
            "netflow",
            "ipfix",
            "pat",
            "vpn",
            "ipsec",
            "isakmp",
            "loopback",
            "subinterface",
            "subinterfaces",
            "match-all",
            "match-any",
            "record",
            "exporter",
            "monitor",
            "flow",
            "access-group",
            "class-map",
            "policy-map",
            "service-policy",
            "deny",
            "sequence",
            "overload",
            "outside",
            "inside",
            "static",
            "mask",
            "prefix-list",
            "route-map",
            "policy-map",
            "class-map",
            "service-policy",
            "tcp",
            "any",
            "all",
            "none",
            "vlan",
            "name",
            "mode",
            "access",
            "trunk",
            "spanning-tree",
            "timers",
            "hello-interval",
            "network",
            "firewall",
            "filter",
            "database",
            "database-filter",
            "term",
            "protocol",
            "family",
            "inet",
            "standard",
            "extended",
            "privilege",
            "snmp",
            "community",
            "allowed",
            "from",
            "to",
            "then",
            "discard",
            "accept",
            "source-address",
            "destination-address",
            "in",
            "out",
            "access-group",
            "access-class",
            "peer-as",
            "group",
            "external",
            "local-address",
            "isakmp",
            "ipsec",
            "esp-aes",
            "esp-sha-hmac",
            "transform-set",
            "peer",
            "nat",
            "overload",
            "inside",
            "outside",
            "vrrp",
            "virtual-address",
            "flow",
            "monitor",
            "exporter",
            "record",
            "collect",
            "counter",
            "bytes",
            "packets",
            "prefix-list",
            "policy-options",
            "idle-timeout",
            "snooping",
            "dhcp",
            "channel-group",
            "lacp",
            "active",
            "passive",
            "passive-interface",
            "redistribute",
            "metric-type",
            "subnets",
            "vrf",
            "static",
            "priority",
            "class",
            "match",
            "ospfv3",
            "preempt",
            "plaintext",
            "flow-export",
            "authentication",
            "null",
            "key",
            "shared",
            "crypto",
            "isakmp",
            "level",
            "destination",
            "source",
            "list",
            "pool",
            "dscp",
            "cs6",
            "orlonger",
            "ipv4",
            "transport",
            "udp",
            "ipfix",
            "version",
            "sys-uptime",
            "first",
            "last",
            "restrict",
            "console",
            "debugging",
            "exec-timeout",
            "login",
            "default",
            "nonegotiate",
            "auto",
            "qos",
            "voip",
            "mls",
            "trust",
            "cos",
            "map",
            "method",
            "algorithm",
            "establish-tunnels",
            "immediately",
            "bind-interface",
            "unit",
            "prefix",
            "input",
            "output",
            "timestamp",
            "authentication-method",
            "pre-shared-keys",
            "ike-policy",
            "ipsec-policy",
            "proposals",
            "authentication-algorithm",
            "long",
            "metric",
            "discard-icmp",
            "icmp",
            "security",
            "ike",
            "proposal",
            "gateway",
            "vpn",
            "external-interface",
            "shutdown",
            "export",
            "perfect-forward-secrecy",
            "keys",
            "group2",
            "df-bit",
            "copy",
            "precedence",
            "percent",
            "bandwidth",
            "track",
            "longer",
            "encapsulation",
            "dot1q",
            "flow-cache",
            "timeout",
            "inactive",
            "ingress",
            "egress",
            "zone",
            "untrust",
            "period",
            "rate",
            "fast",
            "slow",
            "encr",
            "encryption",
            "pre-share",
            "pre-shared",
            "ikev2",
            "esp-sha256-hmac",
            "aes-256",
            "aes-128",
            "sha256",
            "sha1",
            "md5",
            "hash",
            "lifetime",
            "minutes",
            "seconds",
            "hours",
            "kilobytes",
            "diffie-hellman",
            "pfs",
            "ipsec-isakmp",
            "id",
            "security-association",
            "ssh",
            "server",
            "services",
            "protocol-version",
            "encryption-algorithm",
            "authentication-retries",
            "v2",
            "aes128-cbc",
            "dh-group14-sha1",
            "soft-reconfiguration",
            "inbound",
            "outbound",
            "host",
            "public",
            "private",
            "read-only",
            "read-write",
        ]
        LEAF_VERBS = [
            "description",
            "name",
            "password",
            "hostname",
            "banner",
            "alias",
            "remark",
            "community",
            "profile",
            "policy",
            "proposal",
            "transform-set",
            "map",
            "group",
            "class",
            "pool",
            "access-list",
            "prefix-list",
            "route-map",
            "key-exchange-group",
            "vrf",
        ]

        for line in config.splitlines():
            line = line.strip()
            # Skip comments, labels, and empty lines
            if not line or line.startswith(("!", "#", "comment", "```", "**")):
                continue

            # Skip vendor labels like "Cisco:" or "Juniper:"
            if line.endswith(":") and len(line.split()) == 1:
                continue

            # Clean citations from line if LLM included them inside the string
            line_clean = re.sub(r"\[Ref: [^\]]+\]", "", line).strip()

            # Skip if the line is just markdown or common labels after cleaning
            if not line_clean or line_clean.lower() in ["cisco:", "juniper:", "cli:"]:
                continue

            parts = line_clean.split()
            if not parts:
                continue

            structural_tokens = []

            for i, word in enumerate(parts):
                w_lower = word.lower().rstrip(":")

                # If we encounter a leaf verb, stop processing this line.
                # All subsequent tokens are likely user-defined strings.
                if w_lower in LEAF_VERBS:
                    break

                # Robust parameter detection:
                # Keywords should never be treated as parameters
                is_keyword = w_lower in [
                    "vlan",
                    "ospf",
                    "bgp",
                    "router",
                    "interface",
                    "set",
                    "protocols",
                    "mode",
                    "type",
                    "group",
                    "area",
                    "route",
                    "address",
                    "switchport",
                    "neighbor",
                    "nat",
                    "crypto",
                    "isakmp",
                    "ipsec",
                    "vrrp",
                    "flow",
                    "monitor",
                    "prefix-list",
                    "class",
                    "policy-map",
                    "dhcp",
                    "ospfv3",
                    "authentication",
                    "null",
                    "isakmp",
                    "level",
                    "destination",
                    "source",
                    "list",
                    "pool",
                    "dscp",
                    "cs6",
                    "orlonger",
                    "ipv4",
                    "transport",
                    "udp",
                    "ipfix",
                    "version",
                    "restrict",
                    "console",
                    "default",
                    "qos",
                    "trust",
                    "security",
                    "ike",
                    "proposal",
                    "gateway",
                    "vpn",
                    "shutdown",
                    "export",
                    "keys",
                    "copy",
                    "percent",
                    "bandwidth",
                    "encapsulation",
                    "timeout",
                    "port-channel",
                    "port-channels",
                    "etherchannel",
                    "etherchannels",
                    "lacp",
                    "pat",
                    "ipsec",
                    "loopback",
                    "subinterface",
                    "subinterfaces",
                    "match-all",
                    "match-any",
                    "record",
                    "exporter",
                    "class-map",
                    "service-policy",
                    "access-group",
                ]

                # 1. IPs, numbers, and interfaces (digits + punctuation)
                # Improved regex for IPv6 (handles double colons)
                is_numeric_ip = re.match(r"^[0-9.:/a-fA-F]+$", word) is not None and (
                    any(c.isdigit() for c in word) or "::" in word
                )
                # Handle interfaces with hyphens (e.g., fe-1/2/0.6)
                is_interface = re.match(r"^[a-zA-Z-]+[0-9/.]+$", word) is not None

                # 2. User-defined IDs: e.g., CORE-SW-01, PL_SEVEN, discard_icmp, Record1, ExportTest
                # Flag as user ID if it has a separator (-_.), is upper case, contains a digit, or is TitleCase
                has_separator = any(c in word for c in "-_.")
                is_upper = word.isupper() and len(word) > 3
                has_digit = any(c.isdigit() for c in word)
                is_title_case = (
                    len(word) > 1
                    and word[0].isupper()
                    and any(c.islower() for c in word)
                )

                is_user_id = (
                    (has_separator or is_upper or has_digit or is_title_case)
                    and not is_keyword
                    and w_lower not in COMMON_VERBS
                )

                # 3. Present in the intent context (hostnames, names)
                is_in_intent = (
                    len(w_lower) > 2 and w_lower in intent_norm and not is_keyword
                )

                # Split user ID by separators and verify each part is either
                # in the intent, in the common verbs/keywords lists, or numeric.
                is_authorized_user_id = False
                if is_user_id:
                    parts = re.split(r"[-_]", w_lower)
                    all_parts_authorized = True
                    for part in parts:
                        if not part:
                            continue
                        part_in_intent = len(part) > 2 and part in intent_norm
                        part_in_common = (
                            part in COMMON_VERBS
                            or part in NOISY
                            or part
                            in [
                                "vlan",
                                "ospf",
                                "bgp",
                                "router",
                                "interface",
                                "set",
                                "protocols",
                                "mode",
                                "type",
                                "group",
                                "area",
                                "route",
                                "address",
                                "switchport",
                                "neighbor",
                                "nat",
                                "crypto",
                                "isakmp",
                                "ipsec",
                                "vrrp",
                                "flow",
                                "monitor",
                                "prefix-list",
                                "class",
                                "policy-map",
                                "dhcp",
                                "ospfv3",
                                "authentication",
                                "null",
                                "level",
                                "destination",
                                "source",
                                "list",
                                "pool",
                                "dscp",
                                "cs6",
                                "orlonger",
                                "ipv4",
                                "transport",
                                "udp",
                                "ipfix",
                                "version",
                                "restrict",
                                "console",
                                "default",
                                "qos",
                                "trust",
                                "security",
                                "ike",
                                "proposal",
                                "gateway",
                                "vpn",
                                "shutdown",
                                "export",
                                "keys",
                                "copy",
                                "percent",
                                "bandwidth",
                                "encapsulation",
                                "timeout",
                                "class-map",
                                "policy-map",
                                "service-policy",
                                "match-all",
                                "match-any",
                                "record",
                                "exporter",
                                "port-channel",
                            ]
                        )
                        part_numeric = part.isdigit()
                        if not (part_in_intent or part_in_common or part_numeric):
                            all_parts_authorized = False
                            break
                    if all_parts_authorized:
                        is_authorized_user_id = True

                # Only skip user IDs if they are NOT in a structural position (first, second, or third token)
                # This ensures fake protocols/modes like 'switchport mode hyper-virtual' are caught.
                if (
                    is_numeric_ip
                    or is_interface
                    or is_in_intent
                    or is_authorized_user_id
                    or (is_user_id and i >= 3)
                ):
                    continue

                # Skip common noisy tokens
                if w_lower in NOISY:
                    continue

                structural_tokens.append(w_lower)

            if not structural_tokens:
                continue

            # Check if any structural token is completely missing from documentation
            all_tokens_grounded = True
            for token in structural_tokens:
                if (
                    token not in full_doc_text
                    and len(token) > 3
                    and token not in COMMON_VERBS
                ):
                    all_tokens_grounded = False
                    # logger.debug(f"Ungrounded token: {token}")
                    break

            if not all_tokens_grounded:
                ungrounded.append(line_clean)
                logger.info(f"Ungrounded command (token missing): {line_clean}")
                continue

            # Sequence check for common verbs to detect fake protocols/subcommands
            if len(structural_tokens) >= 2:
                primary = structural_tokens[0]
                secondary = structural_tokens[1]
                if primary in COMMON_VERBS and secondary not in COMMON_VERBS:
                    # e.g., "router hyper-ospf"
                    prefix = f"{primary} {secondary}"
                    # Flag if both the combined prefix and the secondary token are missing
                    if prefix not in full_doc_text and secondary not in full_doc_text:
                        logger.info(
                            f"Ungrounded command (sequence missing): {line_clean} | Prefix: {prefix}"
                        )
                        ungrounded.append(line_clean)

        return ungrounded
