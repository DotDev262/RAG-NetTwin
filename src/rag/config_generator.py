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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from rag.vector_store import VectorStore
from rag.multi_vendor_coordinator import MultiVendorCoordinator
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
    citations: List[str] = Field(
        description="List of Source IDs from the DOCUMENTATION block used to ground this config. "
                    "Use ONLY the strings following 'ID: '. Do NOT use document titles."
    )
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
        self.coordinator = MultiVendorCoordinator()
        self._sanity_lock = threading.Lock()

    def generate(
        self, 
        structured_intent: StructuredIntent, 
        retrieval_mode: str = "tiered"
    ) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device.
        retrieval_mode: 'tiered' (ours), 'flat' (standard top-k), or 'none' (baseline).
        """
        configs = {}
        # Recommendation 3: Intent Sanity Check
        configs["_sanity_check"] = {"is_grounded": True, "warnings": []}

        is_lite = self._check_lite_intent(structured_intent)
        if retrieval_mode == "none": is_lite = True # Force baseline for ablation
        
        # Recommendation 2 (Multi-Vendor): Extract shared constraints
        constraints = self.coordinator.extract_shared_constraints(structured_intent)
        coordination_prompt = self.coordinator.build_coordination_prompt(constraints)

        # Build query once for all devices (Optimized: Exclude specific parameter values to avoid query dilution)
        # We keep the protocol and action, and add the parameter KEYS for semantic grounding
        # We only keep parameter values if they look like protocols/keywords (no digits/IPs)
        semantic_params = []
        for k, v in structured_intent.parameters.items():
            semantic_params.append(k)
            # If value is a string and doesn't look like an IP or raw number, it might be a sub-protocol/mode
            if isinstance(v, str) and not re.match(r'^[0-9.:/]+$', v) and len(v) > 2:
                semantic_params.append(v)
        
        query = (
            f"{structured_intent.protocol} {structured_intent.action} "
            + " ".join(semantic_params)
        )

        # 1. Group devices by vendor + version for Consolidated Retrieval
        device_groups = {}
        for device in structured_intent.devices:
            group_key = (device.vendor, self._normalize_version(device))
            if group_key not in device_groups:
                device_groups[group_key] = []
            device_groups[group_key].append(device)

        full_context_map = {}

        # 2. Retrieval Phase
        if not is_lite:
            for (vendor, search_version), devices in device_groups.items():
                # Recommendation 5: Check Semantic Cache first (only in tiered/flat modes)
                if retrieval_mode != "none":
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

                results = []
                
                if retrieval_mode == "tiered":
                    # Balanced Hierarchical Hybrid Retrieval + Reranking (Elite Strategy)
                    # 1. Fetch more candidates (n_results=5) for the Reranker to choose from
                    syntax_candidates = self.vector_store.hybrid_retrieve(
                        query=query, vendor=vendor, os_version=search_version, tier=1, n_results=5
                    )
                    concept_candidates = self.vector_store.hybrid_retrieve(
                        query=query, vendor=vendor, os_version=search_version, tier=2, n_results=5
                    )
                    if not concept_candidates:
                        concept_candidates = self.vector_store.hybrid_retrieve(
                            query=query, vendor=vendor, os_version=search_version, tier=3, n_results=5
                        )
                    
                    # 2. Use local Cross-Encoder to pick the absolute winner for each tier
                    if syntax_candidates:
                        results.extend(self.vector_store.rerank(query, syntax_candidates, n_results=1))
                    if concept_candidates:
                        results.extend(self.vector_store.rerank(query, concept_candidates, n_results=1))
                
                elif retrieval_mode == "flat":
                    # Flat Hybrid + Reranking
                    flat_candidates = self.vector_store.hybrid_retrieve(
                        query=query, vendor=vendor, os_version=search_version, n_results=10
                    )
                    results = self.vector_store.rerank(query, flat_candidates, n_results=2)

                # Recommendation 3: Semantic Sanity Check
                # If similarity scores are too low (distance too high), flag as ungrounded
                if results:
                    # ChromaDB distance > 1.2 usually indicates poor semantic match
                    avg_distance = sum(res.get('distance', 0) for res in results) / len(results)
                    if avg_distance > 1.2:
                        warning = f"Authoritative documentation for '{structured_intent.protocol}' not found for {vendor}. Hallucination risk is high."
                        with self._sanity_lock:
                            configs["_sanity_check"]["warnings"].append(warning)
                            configs["_sanity_check"]["is_grounded"] = False
                else:
                    warning = f"No documentation found in KB for {vendor}/{search_version} '{structured_intent.protocol}'."
                    with self._sanity_lock:
                        configs["_sanity_check"]["warnings"].append(warning)
                        configs["_sanity_check"]["is_grounded"] = False

                if results:
                    # Recommendation Elite: Fetch Parent Grounding Context
                    results = self.vector_store.retrieve_with_parents(results)

                for dev in devices:
                    full_context_map[dev.name] = results
        else:
            logger.info(f"Lite-RAG path activated (Retrieval Mode: {retrieval_mode}).")

        # 3. Generation Phase: Parallelized
        futures = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for device in structured_intent.devices:
                # If already served by cache, skip generation
                if device.name in configs:
                    continue

                # Recommendation 4: Distill context for token efficiency
                device_context = ""
                valid_ids = []
                if device.name in full_context_map:
                    device_context = self.distill_context(full_context_map[device.name])
                    valid_ids = [c.get("id") for c in full_context_map[device.name]]
                
                futures.append(
                    executor.submit(
                        self._generate_single_device, 
                        device, 
                        structured_intent, 
                        device_context,
                        coordination_prompt,
                        valid_ids
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

        # Recommendation 2 (Post-Check): Verify all configs aligned on shared parameters
        alignment_report = self.coordinator.verify_alignment(configs, constraints)
        configs["_interoperability_report"] = alignment_report

        return configs

    def _generate_single_device(
        self,
        device: Any,
        structured_intent: StructuredIntent,
        device_context: str,
        coordination_prompt: str = "",
        valid_source_ids: List[str] = None
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
                    "1. If vendor is Cisco: Use ONLY Cisco IOS-XE syntax.\n"
                    "2. If vendor is Juniper: Use ONLY Juniper JunOS syntax.\n"
                    "3. NEVER mix syntax between vendors.\n"
                    "4. RESPECT all shared constraints provided in the task."
                    "{coordination_prompt}",
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
                    "2. For citations, use the EXACT 'ID: <source_id>' values provided in the documentation block.\n"
                    "3. Output strictly in the requested structured format.\n"
                    "4. CRITICAL: Generate ONLY commands matching the specified vendor.",
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
                "coordination_prompt": coordination_prompt
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
                "valid_source_ids": valid_source_ids or [],
                "grounding_context": device_context,
                "confidence": response.confidence_score,
                "reasoning": response.reasoning_path,
            }
        except Exception as e:
            logger.error(f"Generation failed for {device.name}: {e}")
            return {"device_name": device.name, "config": "ERROR", "error": str(e)}

    def distill_context(self, raw_chunks: List[Dict]) -> str:
        """
        Token Efficiency (Rec 4): Strips noise from PDF chunks using regex.
        Extracts ONLY CLI blocks and key configuration context.
        """
        distilled = ""
        # Regex to find CLI blocks (lines starting with common network keywords or 'set')
        cli_pattern = re.compile(
            r"(?m)^(?:interface|router|ip|ipv6|switchport|vlan|access-list|ntp|logging|snmp|set|firewall|protocols|routing-options|system)\b.*$", 
            re.IGNORECASE
        )
        
        for res in raw_chunks:
            text = res['text']
            # 1. Extract CLI lines
            cli_lines = cli_pattern.findall(text)
            
            # 2. Extract prose that looks like a definition (contains 'is used to' or 'specifies')
            prose_context = []
            for line in text.splitlines():
                if any(k in line.lower() for k in ["is used to", "specifies", "defines", "mandatory"]):
                    prose_context.append(line.strip())
            
            if cli_lines or prose_context:
                distilled += f"ID: {res['id']}\n"
                if cli_lines:
                    distilled += "COMMANDS:\n" + "\n".join(cli_lines[:10]) + "\n"
                if prose_context:
                    distilled += "RULES:\n" + "\n".join(prose_context[:3]) + "\n"
                distilled += "---\n"
                
        return distilled

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
            vendor_lower = (device.vendor or "cisco").lower()
            os_version = "21.4" if vendor_lower == "juniper" else "17.6"

        # Map os_type to KB prefix (handles various naming conventions)
        type_prefix_map = {
            "ios-xe": "ios-xe",
            "junos": "junos",
            "ios": "ios",
            "nxos": "nxos",
            "eos": "eos",
        }

        prefix = type_prefix_map.get(os_type.lower(), os_type.lower())

        # If os_version is missing, default to the most stable version in the KB
        if not os_version:
            if prefix == "ios-xe":
                return "ios-xe-17.6"
            elif prefix == "junos":
                return "junos-21.4"
            return f"{prefix}-latest"

        if os_version.startswith(prefix):
            return os_version

        # Otherwise, combine prefix with version
        # Example: "17.6" + "ios-xe" -> "ios-xe-17.6"
        return f"{prefix}-{os_version}"
