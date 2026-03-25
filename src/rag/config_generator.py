"""
Configuration Generation Module for RAG-NetTwin.

This module handles the generation of network device configurations from
structured intents using a RAG (Retrieval-Augmented Generation) approach.
It retrieves relevant documentation from ChromaDB and uses an LLM to generate
vendor-specific CLI commands.

Key Features:
- Vendor-aware generation (Cisco IOS-XE vs Juniper JunOS)
- Version-locked retrieval for accurate syntax
- Structured output with citations for hallucination mitigation
- Fallback chain for robust retrieval

Typical Usage:
    from parser.intent_parser import IntentParser
    from rag.config_generator import ConfigGenerator

    parser = IntentParser()
    generator = ConfigGenerator()
    intent = parser.parse("Configure OSPF on Router-A")
    config = generator.generate(intent)
"""

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
    """
    Pydantic model for structured configuration output.

    This model defines the expected output format when the LLM generates
    a network device configuration. It ensures the LLM provides commands,
    citations, confidence scores, and reasoning in a consistent format.

    Attributes:
        commands: List of raw CLI configuration commands to apply to the device.
        citations: List of documentation reference IDs used to generate
            the config. These correspond to ChromaDB chunk IDs.
        confidence_score: Float between 0.0 and 1.0 indicating how confident
            the LLM is in the generated config's correctness.
        reasoning_path: Step-by-step explanation of why specific commands
            were chosen and how they satisfy the intent.
        explanation: Optional brief summary of the configuration changes
            being made (e.g., "Enabled OSPF area 0 on router").
    """

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
    """
    Generates network device configurations using RAG and LLM.

    This class orchestrates the configuration generation process by:
    1. Checking if the intent is "lite" (simple, doesn't need RAG retrieval)
    2. Retrieving relevant documentation from ChromaDB based on vendor/version
    3. Using an LLM with structured output to generate CLI commands
    4. Adding citation comments to the config for hallucination traceability

    The generation supports both Cisco IOS-XE and Juniper JunOS syntax,
    with automatic fallback to ensure retrieval always returns some results.

    Attributes:
        llm: Base LLM for refinement tasks (temperature=0 for deterministic output).
        structured_llm: LLM configured with DeviceConfigOutput schema for
            structured generation with citations and confidence scores.
        vector_store: ChromaDB client for retrieval.

    Note:
        Caching is handled at the evaluation level (run_paper_eval.py) to ensure
        consistency with --clear-cache flag and research integrity. This class
        does not implement caching directly.
    """


    def __init__(self, model_name: str = None):
        """
        Initialize the ConfigGenerator.

        Args:
            model_name: Optional model name override. If None, uses the default
                model from LLMProvider configuration.
        """
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.0)
        self.structured_llm = LLMProvider.get_structured_llm(
            schema=DeviceConfigOutput, model=model_name, temperature=0.0
        )
        self.vector_store = VectorStore()

    def generate(self, structured_intent: StructuredIntent) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device using structured output.

        This method implements a two-phase generation approach:

        Phase 1 - Retrieval:
            - Checks if intent is "lite" (show/verify commands, simple tasks)
            - For non-lite intents, retrieves relevant docs from ChromaDB
            - Uses vendor+version filtering for accurate syntax matching
            - Implements fallback chain: vendor+version → vendor only → unfiltered

        Phase 2 - Generation:
            - Builds device-specific prompts with vendor syntax rules
            - Uses structured LLM output for consistent format
            - Adds citation comments using vendor-appropriate syntax
            - Returns configs with confidence scores and reasoning

        Args:
            structured_intent: Parsed intent containing:
                - protocol: Network protocol (e.g., OSPF, BGP, ACL)
                - action: Operation type (create, update, delete, etc.)
                - devices: List of target devices with vendor/os info
                - parameters: Key-value pairs for configuration

        Returns:
            Dict mapping device names to their configuration object containing:
                - config: CLI commands with citation comments
                - retrieved_sources: List of source document IDs used
                - valid_source_ids: Valid ChromaDB chunk IDs from retrieval
                - confidence: Confidence score (0.0-1.0)
                - reasoning: Step-by-step explanation of choices

        Raises:
            Exception: If LLM generation fails for any device. The error
                is logged and an ERROR config is returned for that device.

        Example:
            >>> from parser.intent_parser import IntentParser
            >>> parser = IntentParser()
            >>> generator = ConfigGenerator()
            >>> intent = parser.parse("Configure OSPF area 0 on Router-A")
            >>> configs = generator.generate(intent)
            >>> print(configs["Router-A"]["config"])
        """
        configs = {}

        # Determine if this is a "Lite" intent (simple parameters, common protocols)
        # Lite intents don't need RAG retrieval - they use standard commands
        is_lite = self._check_lite_intent(structured_intent)

        # 1. Retrieval Phase: Fetch documentation from ChromaDB
        # Skip retrieval for lite intents to save tokens and API calls
        full_context_map = {}
        if not is_lite:
            for device in structured_intent.devices:
                # Normalize version to match knowledge base format (e.g., ios-xe-17.6)
                search_version = self._normalize_version(device)

                # Build query from protocol, action, and parameters
                # Example: "ospf create area network router"
                query = (
                    f"{structured_intent.protocol} {structured_intent.action} "
                    + " ".join(structured_intent.parameters.keys())
                )

                # Context Deduplication: Only fetch documentation for this device's specific needs
                # First attempt: vendor + version filtered retrieval
                results = self.vector_store.retrieve(
                    query=query,
                    vendor=device.vendor,
                    os_version=search_version,
                    n_results=2,  # Reduced for token efficiency
                )

                # Fallback 1: Try without version filter but KEEP vendor filter
                # This handles cases where exact version isn't in KB
                if not results:
                    results = self.vector_store.retrieve(
                        query=query, vendor=device.vendor, n_results=2
                    )

                # Fallback 2: Last resort - any vendor but warn about hallucination risk
                # Only used when no vendor-specific docs are available
                if not results:
                    logger.warning(
                        f"No docs found for {device.vendor}/{search_version}, trying unfiltered"
                    )
                    results = self.vector_store.retrieve(query=query, n_results=1)

                full_context_map[device.name] = results
        else:
            logger.info(
                f"Lite-RAG path activated for intent: {structured_intent.original_text[:50]}..."
            )

        # 2. Generation Phase: Generate CLI for each device
        for device in structured_intent.devices:
            # Prepare device-specific context to save tokens
            # Only include retrieved docs for this specific device
            device_context = ""
            if device.name in full_context_map:
                for res in full_context_map[device.name]:
                    device_context += f"ID: {res['id']}\nText: {res['text']}\n---\n"

            # Build prompt with explicit vendor syntax rules
            # Critical: Prevent cross-vendor syntax mixing
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
                # Create LangChain chain with prompt and structured LLM
                # The structured LLM will return a DeviceConfigOutput object
                chain = prompt | self.structured_llm

                # If no RAG context, use base knowledge with explicit instructions
                # This handles lite intents and retrieval failures
                lite_context = (
                    device_context
                    if device_context
                    else f"STANDARD COMMAND: Use your base knowledge of {device.vendor} {device.os_version} CLI syntax. "
                    f"CRITICAL: Generate ONLY {device.vendor} commands. Do NOT mix vendor syntax."
                )

                # Invoke the chain with all required variables
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
                # Join commands into single multiline string
                config_text = "\n".join(response.commands)

                # Add citation comments for "Grounding Audit Trail"
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

                # Build response dict with all metadata
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
        """
        Heuristic to identify simple intents that don't need RAG retrieval.

        Lite intents are simple operations that use standard, well-known commands
        and don't require documentation lookup. These include:
        - Show/verify commands (display-only, no config changes)
        - Simple hostname/description tasks

        Args:
            intent: StructuredIntent to check.

        Returns:
            True if the intent is simple enough to skip RAG retrieval,
            False otherwise.

        Note:
            This is a heuristic - it may occasionally misclassify intents,
            but the fallback in generate() will still work correctly.
        """
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
        """
        Refines a configuration based on validation error feedback.

        This method is called when a configuration fails validation (e.g., from
        Batfish). It uses the error message to fix syntax issues while
        maintaining vendor-specific syntax.

        Args:
            device_name: Name of the device being configured.
            config: The configuration that failed validation.
            error_feedback: Error message from the validator describing what went wrong.
            vendor: Device vendor (e.g., "cisco", "juniper").
            os_version: OS version string. Defaults to "21.4" for Juniper,
                "17.6" for Cisco if not provided.

        Returns:
            Refined configuration string with syntax errors fixed.
        """
        if os_version is None:
            os_version = "21.4" if vendor.lower() == "juniper" else "17.6"

        # Build prompt asking LLM to fix the configuration
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
        """
        Normalize OS version to match knowledge base format.

        The knowledge base stores versions with prefixes like "ios-xe-17.6"
        or "junos-21.4". This method ensures the version string matches
        that format for accurate retrieval.

        Args:
            device: DeviceIntent object with os_type and os_version attributes.

        Returns:
            Normalized version string with prefix (e.g., "ios-xe-17.6").
            Returns "ios-xe-17.6" for Cisco or "junos-21.4" for Juniper
            if version is not specified.

        Examples:
            >>> _normalize_version(DeviceIntent(os_type="ios-xe", os_version="17.6"))
            'ios-xe-17.6'
            >>> _normalize_version(DeviceIntent(os_type="junos", os_version="21.4"))
            'junos-21.4'
            >>> _normalize_version(DeviceIntent(vendor="cisco", os_version=None))
            'ios-xe-17.6'
        """
        os_type = device.os_type or "ios-xe"
        os_version = device.os_version

        # Default to well-tested versions if not specified
        if not os_version:
            os_version = "21.4" if device.vendor.lower() == "juniper" else "17.6"

        # Map os_type to KB prefix (handles various naming conventions)
        type_prefix_map = {
            "ios-xe": "ios-xe",
            "junos": "junos",
            "ios": "ios",
            "nxos": "nxos",
            "eos": "eos",
        }

        prefix = type_prefix_map.get(os_type.lower(), os_type.lower())

        # If os_version already has prefix, return as-is
        # Example: "ios-xe-17.6" stays as "ios-xe-17.6"
        if os_version.startswith(prefix):
            return os_version

        # Otherwise, combine prefix with version
        # Example: "17.6" + "ios-xe" -> "ios-xe-17.6"
        return f"{prefix}-{os_version}"
