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
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    verification_commands: List[str] = Field(
        description="CLI commands to verify the configuration works (e.g., show ip ospf neighbor)",
        default_factory=list
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
        Generates CLI configuration for each device.
        Optimized with Semantic Cache (Rec 5) and Consolidated Retrieval (Rec 3).
        """
        configs = {}
        is_lite = self._check_lite_intent(structured_intent)
        
        # Build query once for all devices
        query = (
            f"{structured_intent.protocol} {structured_intent.action} "
            + " ".join(structured_intent.parameters.keys())
        )

        # 1. Group devices by vendor + version for Consolidated Retrieval (Recommendation 3)
        device_groups = {}
        for device in structured_intent.devices:
            group_key = (device.vendor, self._normalize_version(device))
            if group_key not in device_groups:
                device_groups[group_key] = []
            device_groups[group_key].append(device)

        full_context_map = {}

        # 2. Retrieval Phase (Per Group, not per Device)
        if not is_lite:
            for (vendor, search_version), devices in device_groups.items():
                # Recommendation 5: Check Semantic Cache first
                # We use the first device name as a proxy for the group's needs
                cached_response = self.vector_store.check_cache(
                    structured_intent.original_text, 
                    structured_intent.parameters, 
                    vendor
                )
                
                if cached_response:
                    logger.info(f"Semantic Cache Hit for vendor {vendor}!")
                    for dev in devices:
                        configs[dev.name] = cached_response
                    continue

                # Not in cache, perform retrieval ONCE for the whole group
                results = self.vector_store.retrieve(
                    query=query,
                    vendor=vendor,
                    os_version=search_version,
                    n_results=2,
                )
                
                if not results:
                    results = self.vector_store.retrieve(query=query, vendor=vendor, n_results=2)
                
                if not results:
                    logger.warning(f"No docs found for {vendor}/{search_version}, trying unfiltered")
                    results = self.vector_store.retrieve(query=query, n_results=1)

                for dev in devices:
                    full_context_map[dev.name] = results
        else:
            logger.info(f"Lite-RAG path activated.")

        # 3. Generation Phase: Parallelized with ThreadPoolExecutor (Recommendation 2)
        futures = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for device in structured_intent.devices:
                # If already served by cache, skip generation
                if device.name in configs:
                    continue

                device_context = ""
                if device.name in full_context_map:
                    for res in full_context_map[device.name]:
                        device_context += f"ID: {res['id']}\nText: {res['text']}\n---\n"
                
                futures.append(
                    executor.submit(
                        self._generate_single_device, 
                        device, 
                        structured_intent, 
                        device_context
                    )
                )

            # Collect results as they complete
            for future in as_completed(futures):
                res = future.result()
                device_name = res["device_name"]
                
                # Merge into final configs
                configs[device_name] = res
                
                # Update Semantic Cache
                if res.get("config") != "ERROR":
                    # Find the device vendor for the cache
                    device = next(d for d in structured_intent.devices if d.name == device_name)
                    self.vector_store.update_cache(
                        structured_intent.original_text,
                        structured_intent.parameters,
                        device.vendor,
                        res
                    )

        return configs

    def _generate_single_device(
        self, 
        device: Any, 
        structured_intent: StructuredIntent, 
        device_context: str
    ) -> Dict[str, Any]:
        """
        Helper to generate config for a single device (for parallelization).
        """
        # Build prompt with explicit vendor syntax rules
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an expert {vendor} {os_version} CLI configuration specialist. "
                    "CRITICAL RULES:\n"
                    "1. If vendor is Cisco: Use ONLY Cisco IOS-XE syntax (interface, router ospf, ip route, access-list, etc.)\n"
                    "2. If vendor is Juniper: Use ONLY Juniper JunOS syntax (set interfaces, set protocols ospf, set routing-options, etc.)\n"
                    "3. NEVER mix syntax between vendors.\n"
                    "4. If context contains wrong vendor docs, IGNORE them and use your knowledge of the correct vendor.",
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
                    "1. Use provided documentation for vendor-specific syntax.\n"
                    "2. Output strictly in the requested structured format.\n"
                    "3. CRITICAL: Generate ONLY commands matching the specified vendor.",
                ),
            ]
        )

        try:
            chain = prompt | self.structured_llm
            
            lite_context = (
                device_context if device_context 
                else f"Use your base knowledge of {device.vendor} {device.os_version} syntax."
            )

            response = chain.invoke({
                "intent_params": json.dumps(structured_intent.parameters),
                "intent_text": structured_intent.original_text,
                "device_context": lite_context,
                "device_name": device.name,
                "vendor": device.vendor,
                "os_version": device.os_version or "latest",
            })

            config_text = "\n".join(response.commands)
            comment_char = "#" if (device.vendor or "").lower() == "juniper" else "!"
            
            if response.citations:
                config_text = f"{comment_char} Based on [Ref: {', '.join(response.citations)}]\n" + config_text

            return {
                "device_name": device.name,
                "config": config_text,
                "verification_commands": response.verification_commands or [],
                "retrieved_sources": response.citations or [],
                "confidence": response.confidence_score,
                "reasoning": response.reasoning_path,
            }
        except Exception as e:
            logger.error(f"Generation failed for {device.name}: {e}")
            return {"device_name": device.name, "config": "ERROR", "error": str(e)}

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
