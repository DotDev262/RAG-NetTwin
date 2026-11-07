"""
Structured LLM Extraction Engine for Rule Encoder (rule_encoder/extractor.py).

Implements extraction pipeline using an LLM combined with strict Pydantic structural validation.
Instructs the model to output formal, machine-readable AlignmentSchemaRules from technical specs.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.llm import LLMProvider
from src.rule_encoder.schema import (
    AlignmentRuleSet,
    AlignmentSchemaRule,
    ConstraintType,
    InteroperabilityConstraint,
    ParameterDataType,
    VendorSyntaxMapping,
)
from src.rule_encoder.ingest import DocumentChunk
from src.utils import setup_logger

logger = setup_logger("RuleEncoderExtractor")


class ExtractedRulesPayload(BaseModel):
    """Pydantic model for structured LLM extraction output."""
    rules: List[AlignmentSchemaRule] = Field(
        default_factory=list,
        description="List of formal parameter alignment rules extracted from technical specification"
    )
    extraction_summary: str = Field(
        description="Brief summary of protocol parameters analyzed in this chunk"
    )


class RuleExtractionEngine:
    """
    Offline/Compile-Time LLM Extraction Engine.
    Uses structured LLM output to parse technical chunks into formal AlignmentSchemaRules.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name
        self._llm = None

    def get_structured_llm(self):
        if self._llm is None:
            self._llm = LLMProvider.get_structured_llm(
                schema=ExtractedRulesPayload,
                model=self.model_name,
                temperature=0.0,
            )
        return self._llm

    def extract_from_chunk(
        self,
        chunk: DocumentChunk,
        target_vendors: List[str] = ["cisco", "juniper"],
    ) -> List[AlignmentSchemaRule]:
        """
        Extracts formal alignment rules from a single technical chunk.
        """
        logger.info(f"Extracting alignment rules from chunk [{chunk.chunk_id}]...")

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a Principal Network Standards and Interoperability Architect.\n"
                "Your objective is to extract formal, machine-readable Cross-Vendor Alignment Rules from "
                "RFC protocol specifications and vendor CLI command guides (specifically Cisco IOS-XE and Juniper JunOS).\n\n"
                "### EXTRACTION REQUIREMENTS ###\n"
                "For every protocol parameter mentioned in the document (such as area_id, hello_interval, dead_interval, "
                "md5_key_id, remote_as, mtu, auth_password):\n"
                "1. Protocol Name: Canonical protocol name (e.g. OSPFv2, BGP, RIPv2).\n"
                "2. Parameter Identifier: Normalized snake_case parameter name.\n"
                "3. Vendor Syntax Mapping: Provide CLI command template for each targeted vendor ({target_vendors}).\n"
                "   - Cisco IOS-XE: (e.g. 'ip ospf hello-interval <value>', 'router bgp <asn>', 'neighbor <ip> remote-as <asn>')\n"
                "   - Juniper JunOS / VyOS: (e.g. 'set protocols ospf area <area> hello-interval <value>', 'set protocols bgp neighbor <ip> remote-as <asn>')\n"
                "4. Interoperability Constraints:\n"
                "   - EXACT_MATCH: If the parameter must be strictly identical across the link/session (e.g. OSPF Hello/Dead intervals, Area ID, Auth keys).\n"
                "   - RECIPROCAL_PEER: For BGP peer AS numbers and neighbor addresses.\n"
                "   - SUBNET_MATCH: For link IP addresses.\n"
                "5. Only extract genuine protocol parameters. Do not hallucinate non-existent commands."
            ),
            (
                "human",
                "TECHNICAL SPECIFICATION CHUNK:\n"
                "Source: {source_name}\n"
                "Section: {section_title}\n"
                "Protocol Hint: {protocol_hint}\n"
                "Content:\n{content}\n\n"
                "Target Vendors: {target_vendors}\n\n"
                "Extract all formal parameter alignment rules strictly in the requested schema format."
            ),
        ])

        chain = prompt | self.get_structured_llm()

        try:
            result: ExtractedRulesPayload = chain.invoke({
                "source_name": chunk.source_name,
                "section_title": chunk.section_title,
                "protocol_hint": chunk.protocol_hint or "Network Protocol",
                "content": chunk.content,
                "target_vendors": ", ".join(target_vendors),
            })
            return result.rules
        except Exception as e:
            logger.error(f"Rule extraction failed on chunk {chunk.chunk_id}: {e}")
            return []

    def extract_from_corpus(
        self,
        chunks: List[DocumentChunk],
        target_vendors: List[str] = ["cisco", "juniper"],
    ) -> List[AlignmentSchemaRule]:
        """
        Processes a series of chunks and aggregates extracted alignment rules,
        deduplicating by (protocol_name, parameter_identifier).
        """
        all_rules: List[AlignmentSchemaRule] = []
        seen_keys = set()

        for chunk in chunks:
            rules = self.extract_from_chunk(chunk, target_vendors=target_vendors)
            for rule in rules:
                key = (rule.protocol_name.upper(), rule.parameter_identifier.lower())
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_rules.append(rule)

        logger.info(f"Corpus extraction complete: {len(all_rules)} unique alignment rules generated.")
        return all_rules
