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
    from evaluation.hallucination_detector import HallucinationDetector

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
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


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
    ]

    def detect(
        self, config: str, citations: List[str], valid_source_ids: List[str], 
        retrieved_texts: List[str] = None, intent_context: str = ""
    ) -> HallucinationReport:
        """
        Detect hallucinations in a generated configuration.
        """
        suspicious = []
        invalid_cites = []
        ungrounded = []

        # Step 1: Remove citation references from config
        config_clean = re.sub(r"\[Ref: [^\]]+\]", "", config)

        # Step 2: Check for placeholder patterns
        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, config_clean)
            if matches:
                suspicious.extend(list(set(matches)))

        # Step 3: Check citation validity
        for cite in citations:
            # Clean 'ID: ' prefix if LLM included it (Fix)
            clean_cite = cite.replace("ID:", "").replace("id:", "").strip()
            
            # Flexible citation check: ID match or ID is substring of citation (Flaw Fix)
            found_valid = False
            for valid_id in valid_source_ids:
                if valid_id == clean_cite or valid_id in clean_cite or clean_cite in valid_id:
                    found_valid = True
                    break
            
            if not found_valid and cite:
                invalid_cites.append(cite)

        # Step 4: Command Grounding Check (Recommendation 2)
        if retrieved_texts or intent_context:
            all_docs = (retrieved_texts or [])
            ungrounded = self._check_command_grounding(config_clean, all_docs, intent_context)

        # Determine overall hallucination status
        is_hallucinated = len(suspicious) > 0 or len(invalid_cites) > 0 or len(ungrounded) > 0

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
            reason = "; ".join(reasons)

        return HallucinationReport(
            is_hallucinated=is_hallucinated,
            reason=reason,
            suspicious_commands=suspicious,
            invalid_citations=invalid_cites,
            ungrounded_commands=ungrounded
        )

    def _check_command_grounding(self, config: str, docs: List[str], intent_context: str = "") -> List[str]:
        """
        Robust grounding check: verifies if config tokens are present in documentation 
        OR derived from the user's intent. Prevents false positives on hostnames, 
        IPs, and user-defined identifiers.
        """
        ungrounded = []
        full_doc_text = "\n".join(docs).lower()
        intent_norm = (intent_context or "").lower()
        
        # Noisy tokens that are common parts of commands but not informative for grounding
        NOISY = ["no", "set", "exit", "end", "quit", "commit", "logging", "snmp", "line", "vty", "banner",
                 "enable", "configure", "terminal", "firewall", "filter", "term", "protocols", "interfaces"]
        
        # Verbs that are very common and often grounded by system knowledge
        COMMON_VERBS = ["interface", "router", "ip", "ipv6", "vlan", "access-list", "set", "show", "crypto", "policy", "tunnel", "route", "address"]
        
        # Verbs that take arbitrary user input (leaf nodes)
        LEAF_VERBS = ["description", "name", "password", "hostname", "banner", "alias", "remark"]

        for line in config.splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith(("!", "#", "comment")):
                continue
            
            # Clean citations from line if LLM included them inside the string
            line_clean = re.sub(r"\[Ref: [^\]]+\]", "", line).strip()
            parts = line_clean.split()
            if not parts:
                continue

            # Skip lines starting with "leaf" verbs that take arbitrary strings
            if parts[0].lower() in LEAF_VERBS:
                continue

            # Heuristic: Check if the command structural keywords are grounded.
            # We skip tokens that look like parameters (digits, IPs, or in intent).
            structural_tokens = []
            
            for word in parts:
                w_lower = word.lower()
                
                # Robust parameter detection:
                # Keywords should never be treated as parameters
                is_keyword = w_lower in ["vlan", "ospf", "bgp", "router", "interface", "set", "protocols", "mode", "type", "group", "area", "route", "address"]
                
                # 1. IPs, numbers, and interfaces (digits + punctuation)
                # Improved regex for IPv6 (handles double colons)
                is_numeric_ip = re.match(r'^[0-9.:/a-fA-F]+$', word) is not None and (any(c.isdigit() for c in word) or "::" in word)
                is_interface = re.match(r'^[a-zA-Z]+[0-9/.]+$', word) is not None
                
                # 2. User-defined IDs: e.g., CORE-SW-01, PL_SEVEN
                # Flag as user ID if it has digits+separator OR is upper case (and not a known keyword)
                is_user_id = ((any(c.isdigit() for c in word) and any(c in word for c in "-_.")) or (word.isupper() and len(word) > 3)) and not is_keyword
                
                # 3. Present in the intent context (hostnames, names)
                is_in_intent = (len(w_lower) > 2 and w_lower in intent_norm and not is_keyword)
                
                if is_numeric_ip or is_interface or is_user_id or is_in_intent:
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
                if token not in full_doc_text and len(token) > 3 and token not in COMMON_VERBS:
                    all_tokens_grounded = False
                    break
            
            if not all_tokens_grounded:
                ungrounded.append(line_clean)
                continue

            # Sequence check for common verbs to detect fake protocols/subcommands
            if len(structural_tokens) >= 2:
                primary = structural_tokens[0]
                secondary = structural_tokens[1]
                if primary in COMMON_VERBS:
                    # e.g., "router hyper-ospf"
                    prefix = f"{primary} {secondary}"
                    # Flag if both the combined prefix and the secondary token are missing
                    if prefix not in full_doc_text and secondary not in full_doc_text:
                        ungrounded.append(line_clean)
        
        return ungrounded
