import os
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
import json
import re

from rag.vector_store import VectorStore
from parser.intent_parser import StructuredIntent
from config import settings
from llm import LLMProvider
from utils import clean_cli_prose, setup_logger

logger = setup_logger("ConfigGenerator")


class DeviceConfigOutput(BaseModel):
    """Structured output for network device configuration"""

    commands: List[str] = Field(description="List of raw CLI configuration commands")
    citations: List[str] = Field(description="List of documentation reference IDs used")
    confidence_score: float = Field(
        description="Confidence score (0.0 to 1.0) of the generated config", ge=0, le=1
    )
    reasoning_path: str = Field(
        description="Step-by-step reasoning for the chosen commands"
    )
    explanation: Optional[str] = Field(
        description="Brief summary of the changes", default=None
    )


class ConfigGenerator:
    """Generates network configurations using RAG and LLM."""

    # NOTE: Caching is handled at the evaluation level (run_paper_eval.py)
    # to ensure consistency with --clear-cache flag and research integrity.

    def __init__(self, model_name: str = None):
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.0)
        self.structured_llm = LLMProvider.get_structured_llm(
            schema=DeviceConfigOutput, model=model_name, temperature=0.0
        )
        self.vector_store = VectorStore()

    def generate(self, structured_intent: StructuredIntent) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device using structured output.
        """
        configs = {}

        # Determine if this is a "Lite" intent (simple parameters, common protocols)
        is_lite = self._check_lite_intent(structured_intent)

        # 1. Retrieval (Skip or Optimize)
        full_context_map = {}
        if not is_lite:
            for device in structured_intent.devices:
                search_version = self._normalize_version(device)
                query = (
                    f"{structured_intent.protocol} {structured_intent.action} "
                    + " ".join(structured_intent.parameters.keys())
                )

                # Context Deduplication: Only fetch documentation for this device's specific needs
                results = self.vector_store.retrieve(
                    query=query,
                    vendor=device.vendor,
                    os_version=search_version,
                    n_results=2,  # Reduced for token efficiency
                )
                if not results:
                    # Fallback: try without version filter but KEEP vendor filter
                    results = self.vector_store.retrieve(
                        query=query, vendor=device.vendor, n_results=2
                    )
                if not results:
                    # Last resort: any vendor but warn about potential hallucination risk
                    logger.warning(
                        f"No docs found for {device.vendor}/{search_version}, trying unfiltered"
                    )
                    results = self.vector_store.retrieve(query=query, n_results=1)
                full_context_map[device.name] = results
        else:
            logger.info(
                f"Lite-RAG path activated for intent: {structured_intent.original_text[:50]}..."
            )

        for device in structured_intent.devices:
            # Prepare device-specific context to save tokens
            device_context = ""
            if device.name in full_context_map:
                for res in full_context_map[device.name]:
                    device_context += f"ID: {res['id']}\nText: {res['text']}\n---\n"

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are an expert {vendor} {os_version} CLI configuration specialist. "
                        "CRITICAL RULES:\n"
                        "1. If vendor is Cisco: Use ONLY Cisco IOS-XE syntax (interface, router ospf, ip route, access-list, etc.)\n"
                        "2. If vendor is Juniper: Use ONLY Juniper JunOS syntax (set interfaces, set protocols ospf, set routing-options, etc.)\n"
                        "3. NEVER mix syntax between vendors.\n"
                        "4. If context contains wrong vendor docs, IGNORE them and use your knowledge of the correct vendor.\n"
                        "CISCO examples: interface GigabitEthernet0/1, router bgp 65000, neighbor 10.1.1.1 remote-as 65001, ip access-list extended ACL_NAME\n"
                        "JUNIPER examples: set interfaces ge-0/0/0 unit 0 family inet address 10.1.1.1/24, set protocols ospf area 0.0.0.0 interface ge-0/0/0",
                    ),
                    (
                        "human",
                        "### TASK ###\n"
                        "Device: {device_name} ({vendor} {os_version})\n"
                        "Intent: {intent_text}\n"
                        "Parameters: {intent_params}\n\n"
                        "### DOCUMENTATION ###\n"
                        "{device_context}\n\n"
                        "### INSTRUCTIONS ###\n"
                        "1. If documentation is provided above, prefer it for vendor/version-specific syntax.\n"
                        "2. If no documentation (standard commands), use your base knowledge of {vendor} CLI.\n"
                        "3. Output the data in the required structured format.\n"
                        "4. CRITICAL: Generate ONLY commands matching the specified vendor. Do not mix syntax.",
                    ),
                ]
            )

            try:
                # We need to use the underlying model from the chain to get usage if possible,
                # but LangChain with_structured_output usually returns the object directly.
                # Newer LangChain versions include response metadata.
                chain = prompt | self.structured_llm

                # If no RAG context, use base knowledge with explicit instructions
                lite_context = (
                    device_context
                    if device_context
                    else f"STANDARD COMMAND: Use your base knowledge of {device.vendor} {device.os_version} CLI syntax. "
                    f"CRITICAL: Generate ONLY {device.vendor} commands. Do NOT mix vendor syntax."
                )

                response = chain.invoke(
                    {
                        "intent_params": json.dumps(structured_intent.parameters),
                        "intent_text": structured_intent.original_text,
                        "device_context": lite_context,
                        "device_name": device.name,
                        "vendor": device.vendor,
                        "os_version": device.os_version,
                    }
                )

                # Map structured response back to legacy format for compatibility
                config_text = "\n".join(response.commands)
                # Ensure citations are included as comments in the config for the "Grounding Audit Trail"
                # Use vendor-appropriate comment character: ! for Cisco, # for Juniper
                comment_char = (
                    "#" if (device.vendor or "").lower() == "juniper" else "!"
                )
                if response.citations:
                    citation_text = (
                        f"{comment_char} Based on [Ref: "
                        + ", ".join(response.citations)
                        + "]"
                    )
                    config_text = citation_text + "\n" + config_text

                configs[device.name] = {
                    "config": config_text,
                    "retrieved_sources": response.citations or [],
                    "valid_source_ids": [
                        res["id"] for res in full_context_map.get(device.name, [])
                    ],
                    "confidence": response.confidence_score,
                    "reasoning": response.reasoning_path,
                    "usage": {},  # Placeholder as structured LLM might hide raw usage
                }
            except Exception as e:
                logger.error(f"Generation failed for {device.name}: {e}")
                configs[device.name] = {"config": "ERROR", "error": str(e)}

        return configs

    def _check_lite_intent(self, intent: StructuredIntent) -> bool:
        """Heuristic to identify simple, standard intents that don't need RAG."""
        lite_actions = ["show", "verify"]
        if intent.action.value in lite_actions:
            return True

        # Simple hostname or description tasks
        if intent.protocol and intent.protocol.lower() in ["hostname", "description"]:
            return True

        return False

    def refine(
        self,
        device_name: str,
        config: str,
        error_feedback: str,
        vendor: str,
        os_version: str = None,
    ) -> str:
        if os_version is None:
            os_version = "21.4" if vendor.lower() == "juniper" else "17.6"
        """Refines a configuration based on error feedback."""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a CLI Debugger for {vendor} {os_version}. Fix syntax errors using {vendor} {os_version} CLI syntax. Output ONLY raw CLI commands. NEVER mix syntax from other vendors or versions.",
                ),
                (
                    "human",
                    "Device: {device_name} ({vendor} {os_version})\n"
                    "ERRORS: {error_feedback}\n"
                    "CONFIG TO FIX:\n{config}\n\n"
                    "FIXED CLI (MUST use {vendor} {os_version} syntax):",
                ),
            ]
        )

        response = (prompt | self.llm).invoke(
            {
                "device_name": device_name,
                "config": config,
                "error_feedback": error_feedback,
                "vendor": vendor,
                "os_version": os_version,
            }
        )

        return clean_cli_prose(response.content)

    def _normalize_version(self, device) -> str:
        """Normalize OS version to match KB format (e.g., ios-xe-17.6, junos-21.4)."""
        os_type = device.os_type or "ios-xe"
        os_version = device.os_version

        if not os_version:
            os_version = "21.4" if device.vendor.lower() == "juniper" else "17.6"

        # Map os_type to KB prefix
        type_prefix_map = {
            "ios-xe": "ios-xe",
            "junos": "junos",
            "ios": "ios",
            "nxos": "nxos",
            "eos": "eos",
        }

        prefix = type_prefix_map.get(os_type.lower(), os_type.lower())

        # If os_version already has prefix, return as-is
        if os_version.startswith(prefix):
            return os_version

        # Otherwise, combine prefix with version
        return f"{prefix}-{os_version}"
