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
        r"<PASSWORD\d+>",
        r"<[A-Z_]+\d+>",
        r"ENTER_IP_HERE",
        r"YOUR_AS_NUMBER",
        r"command-not-found",
        r"PLACEHOLDER",
        r"dummy-config",
        r"\[.*?\]",
    ]

    def detect(
        self, config: str, citations: List[str], valid_source_ids: List[str], retrieved_texts: List[str] = None
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
            if cite not in valid_source_ids:
                invalid_cites.append(cite)

        # Step 4: Command Grounding Check (Recommendation 2)
        if retrieved_texts:
            ungrounded = self._check_command_grounding(config_clean, retrieved_texts)

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

    def _check_command_grounding(self, config: str, docs: List[str]) -> List[str]:
        """
        Check if CLI keywords in config are present in the retrieved docs.
        """
        ungrounded = []
        full_doc_text = "\n".join(docs).lower()
        
        # Simple heuristic: extract commands (first 2-3 words of each line)
        for line in config.splitlines():
            line = line.strip()
            if not line or line.startswith(("!", "#", "comment")):
                continue
            
            # Extract keywords (e.g., "router ospf", "interface gigabitethernet")
            # We ignore numbers/IPs/params at the end
            parts = line.split()
            if len(parts) >= 2:
                # Try 2-word keyword match (e.g., "router ospf")
                keyword = f"{parts[0]} {parts[1]}".lower()
                # Remove version numbers if present (e.g., "ospf 1" -> "ospf")
                keyword = re.sub(r"\d+", "", keyword).strip()
                
                if keyword not in full_doc_text:
                    ungrounded.append(line)
            elif len(parts) == 1:
                # Try 1-word keyword match (e.g., "exit")
                keyword = parts[0].lower()
                if keyword not in full_doc_text and len(keyword) > 3:
                    ungrounded.append(line)
        
        return ungrounded
