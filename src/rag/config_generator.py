import os
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
import json
import re

from rag.vector_store import VectorStore
from parser.intent_parser import StructuredIntent
from config import settings
from llm import LLMProvider


class ConfigGenerator:
    """Generates network configurations using RAG and LLM."""

    def __init__(self, model_name: str = None):
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.0)
        self.vector_store = VectorStore()

    def generate(self, structured_intent: StructuredIntent) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device using Chain-of-Thought prompting.
        """
        configs = {}
        
        # 1. Retrieval
        full_context_map = {}
        for device in structured_intent.devices:
            search_version = self._normalize_version(device)
            query = f"{structured_intent.protocol} {structured_intent.action} " + " ".join(structured_intent.parameters.keys())
            results = self.vector_store.retrieve(query=query, vendor=device.vendor, os_version=search_version, n_results=3)
            if not results:
                results = self.vector_store.retrieve(query=query, n_results=2)
            full_context_map[device.name] = results

        # 2. Coordinated Generation
        all_contexts_text = ""
        for dev_name, results in full_context_map.items():
            all_contexts_text += f"\n### Documentation for {dev_name} ###\n"
            for res in results:
                all_contexts_text += f"ID: {res['id']}\nText: {res['text']}\n---\n"

        for device in structured_intent.devices:
            # CHAIN-OF-THOUGHT PROMPT: Forces the model to plan before coding
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "You are a professional Network CLI Expert. Follow the steps: 1. Parameters, 2. Documentation Match, 3. CLI Synthesis."),
                    (
                        "human",
                        "### TASK ###\n"
                        "Device: {device_name} ({vendor} {os_version})\n"
                        "Intent: {intent_text}\n"
                        "Parameters: {intent_params}\n\n"
                        "### DOCUMENTATION ###\n"
                        "{coordinated_context}\n\n"
                        "### INSTRUCTIONS ###\n"
                        "Step 1: List the IP addresses and interface names from the Intent.\n"
                        "Step 2: Identify which Reference ID contains the correct command syntax.\n"
                        "Step 3: Generate the raw CLI commands. Output ONLY the CLI commands and citations. NO prose.\n\n"
                        "CLI Synthesis:"
                    ),
                ]
            )

            response = (prompt | self.llm).invoke(
                {
                    "intent_params": json.dumps(structured_intent.parameters),
                    "intent_text": structured_intent.original_text,
                    "coordinated_context": all_contexts_text,
                    "device_name": device.name,
                    "vendor": device.vendor,
                    "os_version": device.os_version,
                }
            )

            # Clean response using improved regex
            content = self._force_strip_prose(response.content)
            
            configs[device.name] = {
                "config": content,
                "retrieved_sources": [r["id"] for r in full_context_map[device.name]],
            }

        return configs

    def refine(self, device_name: str, config: str, error_feedback: str, vendor: str) -> str:
        """Refines a configuration based on error feedback."""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a CLI Debugger. Fix syntax errors. Output ONLY CLI."),
                (
                    "human",
                    "Device: {device_name}\n"
                    "ERRORS: {error_feedback}\n"
                    "CONFIG TO FIX:\n{config}\n\n"
                    "FIXED CLI:"
                ),
            ]
        )

        response = (prompt | self.llm).invoke({
            "device_name": device_name,
            "config": config,
            "error_feedback": error_feedback
        })
        
        return self._force_strip_prose(response.content)

    def _force_strip_prose(self, text: str) -> str:
        import re
        # Aggressive removal of "Assistant:", "Note:", etc.
        text = re.sub(r"^(Assistant|Note|Sure|Here|System|User|Task|CLI|Device|Intent|Documentation|Step \d):.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r"```[a-z]*\n", "", text)
        text = text.replace("```", "")
        
        lines = text.split("\n")
        cleaned_lines = []
        valid_starts = (
            "interface", "router", "ip ", "ipv6 ", "no ", "description", "set ", 
            "configure", "policy-options", "routing-options", "protocols", 
            "system", "snmp", "logging", "ntp", "user", "username", "access-list",
            "!", "exit", "quit", "commit", "apply", "firewall", "vlan", "spanning-tree",
            "area ", "network ", "neighbor ", "address-family", "route-map", "prefix-list",
            "hostname ", "banner ", "term ", "from ", "then ", "edit ", "family "
        )
        
        seen_lines = set()
        for line in lines:
            trimmed = line.strip()
            if not trimmed: continue
            
            # Preserve citations
            if trimmed.startswith("!"):
                cleaned_lines.append(line)
                continue
                
            # Case-insensitive start check
            lower_line = trimmed.lower()
            if any(lower_line.startswith(s) for s in valid_starts):
                # Aggressive deduplication to prevent model loops
                if trimmed not in seen_lines:
                    cleaned_lines.append(line)
                    seen_lines.add(trimmed)
        
        result = "\n".join(cleaned_lines).strip()
        if not result and text.strip():
            # If all else fails, return lines that are short (unlikely to be prose)
            return "\n".join([l for l in text.split("\n") if 0 < len(l.split()) < 10]).strip()
        return result

    def _normalize_version(self, device) -> str:
        search_version = device.os_version
        if device.os_type == "ios-xe" and "17.6" in search_version:
            return "ios-xe-17.6"
        elif device.os_type == "junos" and "21.4" in search_version:
            return "junos-21.4"
        return search_version
