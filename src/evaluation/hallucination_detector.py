import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class HallucinationReport(BaseModel):
    is_hallucinated: bool
    reason: Optional[str] = None
    suspicious_commands: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)


class HallucinationDetector:
    """Detects common LLM hallucinations in network configs."""

    # Common hallucinated commands or placeholders
    HALLUCINATION_PATTERNS = [
        r"<YOUR_[A-Z_]+>",  # <YOUR_PASSWORD>, <YOUR_IP>, etc.
        r"<ENTER_[A-Z_]+>",  # <ENTER_IP>, <ENTER_AS>, etc.
        r"<SAMPLE_[A-Z_]+>",  # <SAMPLE_IP>, etc.
        r"<EXAMPLE_[A-Z_]+>",  # <EXAMPLE_IP>, etc.
        r"<CHANGE_ME>",  # <CHANGE_ME>
        r"<REPLACE_[A-Z_]+>",  # <REPLACE_THIS>
        r"<PASSWORD\d+>",  # <PASSWORD1>, <PASSWORD123>, etc.
        r"<[A-Z_]+\d+>",  # Generic ALL CAPS with numbers like <AS123>
        r"ENTER_IP_HERE",
        r"YOUR_AS_NUMBER",
        r"command-not-found",
        r"PLACEHOLDER",
        r"dummy-config",
        r"\[.*?\]",  # Square brackets (but exclude citations)
    ]

    def detect(
        self, config: str, citations: List[str], valid_source_ids: List[str]
    ) -> HallucinationReport:
        suspicious = []
        invalid_cites = []

        # 1. First, remove citation references from config to avoid false positives
        config_clean = re.sub(r"\[Ref: [^\]]+\]", "", config)

        # 2. Check for placeholders in cleaned config
        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, config_clean)
            if matches:
                suspicious.extend(matches)

        # 2. Check for citation validity
        for cite in citations:
            if cite not in valid_source_ids:
                invalid_cites.append(cite)

        is_hallucinated = len(suspicious) > 0 or len(invalid_cites) > 0
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
