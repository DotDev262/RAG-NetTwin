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
            True if suspicious commands OR invalid citations found.
        reason: Human-readable explanation of why detection failed.
            None if no hallucinations detected.
        suspicious_commands: List of detected placeholder patterns
            (e.g., ["<YOUR_IP>", "<ENTER_AS>"]).
        invalid_citations: List of citation IDs that don't match
            retrieved sources (indicates citation fabrication).
    """

    is_hallucinated: bool
    reason: Optional[str] = None
    suspicious_commands: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)


class HallucinationDetector:
    """
    Detects common LLM hallucinations in network configurations.

    This detector identifies two types of hallucinations:
    1. Placeholder Hallucinations: LLM uses placeholder values instead of
       actual configuration (e.g., <YOUR_IP> instead of 192.168.1.1)
    2. Citation Hallucinations: LLM cites sources that weren't actually
       retrieved, which could indicate the config wasn't grounded

    The detector uses regex patterns to identify common placeholder formats
    and validates that cited sources exist in the retrieved results.

    Attributes:
        HALLUCINATION_PATTERNS: List of regex patterns for detecting
            common placeholder formats. These are ordered by specificity
            from most specific to most general.

    False Positive Handling:
        - Citation brackets [Ref: ...] are removed before pattern matching
        - Valid Cisco syntax like <password> is NOT flagged (only <YOUR_PASSWORD>)
    """

    # Common hallucinated commands or placeholders
    # Ordered from specific to general to catch most common cases first
    HALLUCINATION_PATTERNS = [
        r"<YOUR_[A-Z_]+>",  # <YOUR_PASSWORD>, <YOUR_IP>, etc.
        r"<ENTER_[A-Z_]+>",  # <ENTER_IP>, <ENTER_AS>, etc.
        r"<SAMPLE_[A-Z_]+>",  # <SAMPLE_IP>, etc.
        r"<EXAMPLE_[A-Z_]+>",  # <EXAMPLE_IP>, etc.
        r"<CHANGE_ME>",  # <CHANGE_ME>
        r"<REPLACE_[A-Z_]+>",  # <REPLACE_THIS>
        r"<PASSWORD\d+>",  # <PASSWORD1>, <PASSWORD123>, etc. (numeric suffixes)
        r"<[A-Z_]+\d+>",  # Generic ALL CAPS with numbers like <AS123>
        r"ENTER_IP_HERE",  # Standalone placeholders
        r"YOUR_AS_NUMBER",
        r"command-not-found",  # Command failure indicator
        r"PLACEHOLDER",  # Generic placeholder
        r"dummy-config",  # Dummy configuration marker
        r"\[.*?\]",  # Square brackets (but exclude citations - handled separately)
    ]

    def detect(
        self, config: str, citations: List[str], valid_source_ids: List[str]
    ) -> HallucinationReport:
        """
        Detect hallucinations in a generated configuration.

        This method performs two checks:
        1. Pattern matching: Scan for placeholder patterns in the config
        2. Citation validation: Ensure all cited sources exist in valid sources

        Args:
            config: The generated configuration text to analyze.
            citations: List of citation IDs from the LLM response.
            valid_source_ids: List of valid source IDs from RAG retrieval.
                These are the IDs of actually retrieved chunks.

        Returns:
            HallucinationReport containing:
                - is_hallucinated: True if any issues found
                - reason: Explanation if hallucinated, None otherwise
                - suspicious_commands: List of detected placeholders
                - invalid_citations: List of citations not in valid sources

        Example:
            >>> detector = HallucinationDetector()
            >>> report = detector.detect(
            ...     config="ip address <YOUR_IP> 255.255.255.0",
            ...     citations=["src_001"],
            ...     valid_source_ids=["src_001", "src_002"]
            ... )
            >>> report.is_hallucinated
            True
            >>> report.suspicious_commands
            ['<YOUR_IP>']
        """
        suspicious = []
        invalid_cites = []

        # Step 1: Remove citation references from config to avoid false positives
        # The pattern [Ref: ...] contains square brackets that would match
        # our generic pattern, so we strip them before pattern matching
        config_clean = re.sub(r"\[Ref: [^\]]+\]", "", config)

        # Step 2: Check for placeholder patterns in cleaned config
        # Iterate through all hallucination patterns and collect matches
        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, config_clean)
            if matches:
                # Extend with unique matches (set to deduplicate)
                suspicious.extend(list(set(matches)))

        # Step 3: Check citation validity
        # If LLM cites sources that weren't retrieved, that's suspicious
        # This could indicate the LLM fabricated citations
        for cite in citations:
            if cite not in valid_source_ids:
                invalid_cites.append(cite)

        # Determine overall hallucination status
        is_hallucinated = len(suspicious) > 0 or len(invalid_cites) > 0

        # Build reason string if hallucinations detected
        reason = None
        if is_hallucinated:
            reasons = []
            if suspicious:
                reasons.append(f"Placeholders found: {suspicious}")
            if invalid_cites:
                reasons.append(f"Invalid citations: {invalid_cites}")
            reason = "; ".join(reasons)

        return HallucinationReport(
            is_hallucinated=is_hallucinated,
            reason=reason,
            suspicious_commands=suspicious,
            invalid_citations=invalid_cites,
        )
