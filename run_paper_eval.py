"""
Paper Evaluation Module for RAG-NetTwin.

This module provides comprehensive evaluation capabilities for measuring
RAG-NetTwin's performance against research metrics. It compares the
RAG-NetTwin approach against vanilla LLM baselines and generates
structured reports for paper writing.

Key Features:
- Dual-mode evaluation (Vanilla LLM vs RAG-NetTwin)
- Multi-tier validation (syntactic, semantic, CFR faithfulness)
- Hallucination detection with citation validation
- Caching with 7-day expiry for efficient re-runs
- Latency tracking per intent
- Historical result tracking

Metrics Computed:
- Syntactic Validity: % of configs passing Batfish validation
- Hallucination Rate: % of configs with detected hallucinations
- CFR Faithfulness: % of configs containing all required parameters
- Average Latency: Time per configuration generation

Typical Usage:
    # RAG-Only mode (default)
    uv run python run_paper_eval.py

    # With vanilla LLM comparison
    uv run python run_paper_eval.py --run-vanilla

    # Use cached results only
    uv run python run_paper_eval.py --cache-only
"""

import json
import time
import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from llm import LLMProvider
from config import settings
from evaluation.hallucination_detector import HallucinationDetector
from evaluation.ensemble import EnsembleEngine
from utils import setup_logger, TokenCounter

logger = setup_logger("PaperEval")

# SECURITY NOTE: Cache files contain full network configurations in plain text.
# This is acceptable for research environments only. For production:
# - Implement encryption at rest, or
# - Scrub sensitive parameters (passwords, keys) before caching, or
# - Use secure storage with access controls

# Cache file paths for evaluation results
VANILLA_CACHE_FILE = "results/vanilla_cache.json"
RAG_CACHE_FILE = "results/rag_cache.json"

# Cache entries older than this are considered stale
CACHE_EXPIRY_DAYS = 7


class PaperQualityEvaluator:
    """
    Optimized high-scale evaluation script for RAG-NetTwin.

    This class orchestrates the complete evaluation pipeline for measuring
    RAG-NetTwin's performance. It generates network configurations from
    natural language intents using both the RAG-NetTwin system and a
    vanilla LLM baseline, then validates them using Batfish.

    The evaluator supports caching to enable efficient re-runs and
    produces structured JSON reports for analysis.

    Attributes:
        parser: IntentParser instance for NL to StructuredIntent conversion.
        generator: ConfigGenerator instance for RAG-based config generation.
        validator: BatfishValidator instance for syntactic validation.
        hallucination_detector: HallucinationDetector for hallucination checks.
        ensemble: EnsembleEngine (reserved for future use).
        token_counter: TokenCounter for tracking API usage and costs.
        vanilla_llm: Optional LLM for baseline comparison.
        vanilla_cache: Dictionary of cached vanilla results.
        rag_cache: Dictionary of cached RAG results.

    Evaluation Flow:
        1. Pre-flight check: Verify Batfish connectivity
        2. Batch parsing: Convert all test intents to StructuredIntent
        3. Generation & Validation: For each intent:
           a. Generate config (RAG-NetTwin + optional Vanilla)
           b. Validate with Batfish
           c. Check CFR faithfulness
           d. Detect hallucinations
        4. Cache results and generate summary

    Example:
        >>> evaluator = PaperQualityEvaluator(run_vanilla=True)
        >>> evaluator.run_full_eval()
    """

    def __init__(self, run_vanilla: bool = False, cache_only: bool = False):
        """
        Initialize the PaperQualityEvaluator.

        Args:
            run_vanilla: Whether to also run vanilla LLM baseline for comparison.
            cache_only: If True, only use cached results (no new API calls).
        """
        self.parser = IntentParser()
        self.generator = ConfigGenerator()
        self.validator = BatfishValidator()
        self.hallucination_detector = HallucinationDetector()
        self.ensemble = EnsembleEngine()
        self.token_counter = TokenCounter()
        self.vanilla_llm = LLMProvider.get_llm(temperature=0.0) if run_vanilla else None
        self.run_vanilla = run_vanilla
        self.cache_only = cache_only

        # Load caches from disk
        self.vanilla_cache = self._load_cache(VANILLA_CACHE_FILE)
        self.rag_cache = self._load_cache(RAG_CACHE_FILE)

        os.makedirs("results", exist_ok=True)
        logger.info(f"Loaded vanilla cache: {len(self.vanilla_cache)} items")
        logger.info(f"Loaded RAG cache: {len(self.rag_cache)} items")

    def _load_cache(self, filepath: str) -> Dict[str, Any]:
        """
        Load cache file, filtering out expired entries.

        Entries older than CACHE_EXPIRY_DAYS are considered stale and excluded.
        This ensures evaluation results remain fresh while enabling fast re-runs.

        Args:
            filepath: Path to the cache JSON file.

        Returns:
            Dictionary of cache entries (excluding expired ones).
        """
        if not os.path.exists(filepath):
            return {}

        try:
            with open(filepath, "r") as f:
                cache = json.load(f)

            # Filter out expired entries (including those without timestamps - mark as stale)
            cutoff = datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS)
            filtered = {}
            for key, value in cache.items():
                ts = value.get("timestamp", "")
                if ts:
                    try:
                        entry_time = datetime.fromisoformat(ts)
                        if entry_time > cutoff:
                            filtered[key] = value
                        # Entries without valid timestamp are NOT included (they're stale)
                    except:
                        # Invalid timestamp format - treat as stale, don't include
                        pass
                # Entries without timestamp are also stale - don't include

            expired_count = len(cache) - len(filtered)
            if expired_count > 0:
                logger.info(f"Filtered out {expired_count} expired cache entries")
            return filtered
        except Exception as e:
            logger.warning(f"Failed to load cache {filepath}: {e}")
            return {}

    def _save_cache(self, filepath: str, cache: Dict[str, Any]):
        """
        Save cache to file.

        Args:
            filepath: Path to save the cache JSON file.
            cache: Dictionary of cache entries to save.
        """
        try:
            with open(filepath, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache {filepath}: {e}")

    def _cache_get(self, cache: Dict, key: str) -> Optional[Any]:
        """
        Get from cache if exists and not expired.

        Args:
            cache: Cache dictionary to search.
            key: Cache key to look up.

        Returns:
            Cached value if exists and not expired, None otherwise.
        """
        if key not in cache:
            return None
        ts = cache[key].get("timestamp", "")
        if ts:
            try:
                entry_time = datetime.fromisoformat(ts)
                if entry_time < datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS):
                    return None
            except:
                pass
        return cache[key]

    def _cache_set(self, cache: Dict, key: str, value: Any):
        """
        Store value in cache with timestamp.

        Args:
            cache: Cache dictionary to update.
            key: Cache key.
            value: Value to store.
        """
        cache[key] = {**value, "timestamp": datetime.now().isoformat()}

    def get_intent_key(self, intent) -> str:
        """
        Generate a cache key for an intent.

        Args:
            intent: StructuredIntent object to generate key for.

        Returns:
            String key based on original text.
        """
        return intent.original_text if hasattr(intent, "original_text") else str(intent)

    def get_test_intents(self) -> List[str]:
        """
        Get the list of test intents for evaluation.

        This is a curated list of 23 network configuration intents
        covering various protocols, vendors, and complexity levels.
        The list is kept static for longitudinal tracking consistency.

        Returns:
            List of natural language intent strings.
        """
        # (Keeping original list for consistency in longitudinal tracking)
        return [
            "Configure OSPF area 0 on Gig1/0/1 with IP 10.10.10.1/24",
            "Set up BGP with neighbor 192.168.50.1 remote-as 65000 on Cisco",
            "Configure static route to 172.16.0.0/16 via 10.0.0.1",
            "Enable OSPF process 10 on all active interfaces for Juniper",
            "Set router-id 1.1.1.1 for OSPF on Cisco IOS-XE 17.6",
            "Create an ACL named BLOCK_WEB to deny TCP port 80 from any source",
            "Configure a firewall filter on Juniper to discard ICMP from 10.0.0.0/8",
            "Apply access-list 101 inbound on interface GigabitEthernet0/1",
            "Restrict SSH access to only 192.168.1.0/24 subnet on Cisco",
            "Create a standard ACL 10 to permit only 10.1.1.0/24",
            "Set description 'Uplink to Core' on interface Gig0/0",
            "Configure VLAN 100 named 'DATABASE' on Cisco switch",
            "Enable LLDP globally on a Juniper EX switch",
            "Set interface MTU to 9000 for jumbo frames on Cisco IOS-XE",
            "Configure trunk port on Gig1/0/24 allowing VLANs 10,20,30",
            "Configure OSPF area 0 between Cisco (17.6) and Juniper (21.4) on their shared link",
            "Set up a BGP peering between Cisco AS 65001 and Juniper AS 65002",
            "Align OSPF hello-interval to 5 seconds on both Cisco and Juniper routers",
            "Set system hostname to CORE-RTR-01",
            "Configure NTP server 10.1.1.100 on Cisco IOS-XE",
            "Enable SNMP community 'public' with RO access",
            "Set up local user 'admin' with secret 'Cisco123' and level 15",
            "Configure logging buffer size to 100000",
        ]

    def run_full_eval(self):
        """
        Run the complete evaluation pipeline.

        This is the main entry point for evaluation. It:
        1. Verifies Batfish connectivity (pre-flight check)
        2. Loads test intents
        3. Batch parses intents to StructuredIntent format
        4. Generates and validates configs for each intent
        5. Caches results and saves to JSON
        6. Generates summary table

        The evaluation will exit with error if Batfish is not available.
        """
        # --- PRE-FLIGHT CHECK ---
        logger.info("Pre-flight check: Verifying Batfish connectivity...")
        try:
            # We check if session is initialized and try a lightweight operation
            if not self.validator.session:
                raise ConnectionError("Batfish session not initialized.")

            # list_networks() is a fast way to check if the service is actually responsive
            self.validator.session.list_networks()
            logger.info("Batfish detected and responsive.")
        except Exception as e:
            print("\n" + "=" * 60)
            print("ERROR: BATFISH IS OFFLINE")
            print("Paper evaluation requires Batfish for Tier 1 Syntactic Validation.")
            print("\nPlease start Batfish using Docker:")
            print(
                "docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish"
            )
            print("=" * 60 + "\n")
            sys.exit(1)
        # ------------------------

        scenarios = self.get_test_intents()
        all_results = []

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        metadata = {
            "timestamp": timestamp,
            "llm_provider": settings.llm_provider,
            "embedding_model": settings.embedding_model_name,
            "prompt_version": "v3.0-pydantic-structured",
            "run_vanilla": self.run_vanilla,
            "cache_only": self.cache_only,
        }

        # 1. BATCH PARSING (Optimized)
        logger.info(f"Phase 1: Batch parsing {len(scenarios)} intents...")
        try:
            parsed_intents = self.parser.parse_batch(scenarios)
        except Exception as e:
            logger.error(f"Batch parsing failed: {e}. Falling back to sequential.")
            parsed_intents = [self.parser.parse(s) for s in scenarios]

        # 2. GENERATION & VALIDATION
        eval_mode = "RAG-Only" if not self.run_vanilla else "Both"
        logger.info(
            f"Phase 2: Generating and Validating configurations... ({eval_mode})"
        )

        cached_count = 0
        new_count = 0
        for intent in tqdm(parsed_intents, desc="Evaluating Intents"):
            res = self.evaluate_intent(intent)
            if res:
                all_results.append(res)
                intent_key = self.get_intent_key(intent)
                if intent_key in self.rag_cache:
                    cached_count += 1
                else:
                    new_count += 1
            time.sleep(0.2)  # Balanced delay to avoid rate limits

        logger.info(f"Cache stats: {cached_count} cached, {new_count} new")

        # 3. SAVE & SUMMARIZE
        os.makedirs("results/history", exist_ok=True)
        report = {
            "metadata": metadata,
            "results": all_results,
            "total_tokens": self.token_counter.get_total_usage().model_dump(),
        }

        with open("results/paper_evaluation_latest.json", "w") as f:
            json.dump(report, f, indent=2)

        history_path = f"results/history/eval_{timestamp}.json"
        with open(history_path, "w") as f:
            json.dump(report, f, indent=2)

        # Save caches
        self._save_cache(VANILLA_CACHE_FILE, self.vanilla_cache)
        self._save_cache(RAG_CACHE_FILE, self.rag_cache)
        logger.info(f"Saved caches to {VANILLA_CACHE_FILE} and {RAG_CACHE_FILE}")

        logger.info(f"Evaluation saved to {history_path}")
        self._generate_summary_table(all_results)

    def evaluate_intent(self, intent):
        """
        Evaluate a single intent through both vanilla and RAG pipelines.

        This method generates configurations using both approaches (if enabled),
        validates them with Batfish, checks CFR faithfulness, and detects
        hallucinations. Results are cached for future runs.

        Args:
            intent: StructuredIntent to evaluate.

        Returns:
            Dictionary containing evaluation results for both modes.
        """
        intent_key = self.get_intent_key(intent)
        results = {
            "scenario": intent.original_text,
            "parsed_intent": intent.model_dump(),
        }

        # --- MODE A: VANILLA LLM (optional) ---
        if self.run_vanilla and not self.cache_only:
            # Check cache first
            cached_vanilla = self._cache_get(self.vanilla_cache, intent_key)
            if cached_vanilla:
                results["vanilla"] = cached_vanilla
                logger.info(f"Vanilla cache hit: {intent_key[:40]}...")
            else:
                try:
                    vanilla_cfg = self._generate_vanilla(intent.original_text)
                    validation = self.validator.validate(
                        {"Vanilla-Router": vanilla_cfg}
                    )
                    vanilla_result = {
                        "config": vanilla_cfg,
                        "status": validation["status"],
                        "cfr_failure": self._check_cfr(intent, vanilla_cfg),
                        "hallucination": self.hallucination_detector.detect(
                            vanilla_cfg, [], []
                        ).model_dump(),
                    }
                    results["vanilla"] = vanilla_result
                    self._cache_set(self.vanilla_cache, intent_key, vanilla_result)
                except Exception as e:
                    results["vanilla"] = {"status": "ERROR", "error": str(e)}

        # --- MODE B: RAG-NetTwin (Structured + Lite Path) ---
        # Check cache first
        cached_rag = self._cache_get(self.rag_cache, intent_key)
        if cached_rag:
            results["rag_nettwin"] = cached_rag
            logger.info(f"RAG cache hit: {intent_key[:40]}...")
        elif self.cache_only:
            results["rag_nettwin"] = {"status": "SKIPPED", "reason": "cache_only mode"}
        else:
            try:
                start_time = time.time()
                rag_output = self.generator.generate(intent)
                elapsed = time.time() - start_time
                # Normalize latency per device for fair comparison
                num_devices = len(rag_output)
                latency = elapsed / num_devices if num_devices > 0 else elapsed

                full_config_map = {
                    name: data["config"] for name, data in rag_output.items()
                }
                validation = self.validator.validate(full_config_map, intent)

                # Use detector for paper-grade hallucination stats
                hal_reports = [
                    self.hallucination_detector.detect(
                        data["config"],
                        data.get("retrieved_sources", []),
                        data.get("valid_source_ids", []),
                    ).model_dump()
                    for data in rag_output.values()
                ]

                rag_result = {
                    "configs": full_config_map,
                    "validation": validation,
                    "latency": latency,
                    "cfr_failure": self._check_cfr(
                        intent, "\n".join(full_config_map.values())
                    ),
                    "hallucinations": hal_reports,
                    "confidence_avg": sum(
                        d.get("confidence", 0) for d in rag_output.values()
                    )
                    / len(rag_output)
                    if rag_output
                    else 0,
                }
                results["rag_nettwin"] = rag_result
                self._cache_set(self.rag_cache, intent_key, rag_result)
            except Exception as e:
                logger.error(
                    f"RAG evaluation failed for {intent.original_text[:30]}: {e}"
                )
                results["rag_nettwin"] = {"status": "ERROR", "error": str(e)}

        return results

    def _generate_vanilla(self, scenario: str) -> str:
        """
        Generate configuration using vanilla LLM (no RAG).

        This is the baseline approach that generates configs without
        retrieval-augmented generation, used for comparison.

        Args:
            scenario: Natural language intent string.

        Returns:
            Generated CLI configuration string.
        """
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_template(
            "Task: Generate Cisco/Juniper CLI for {request}. Output ONLY the raw commands. NO prose. CLI:"
        )
        chain = prompt | self.vanilla_llm
        return chain.invoke({"request": scenario}).content

    def _check_cfr(self, intent, config: str) -> bool:
        """
        CFR Check: Detects if critical intent parameters are missing in configs.

        CFR (Config Faithfulness Rate) measures whether the generated config
        includes all the critical parameters specified in the intent.
        This catches cases where the LLM omits important values like
        IP addresses, VLAN IDs, AS numbers, etc.

        Args:
            intent: StructuredIntent with parameters to check.
            config: Generated configuration string.

        Returns:
            True if any critical parameter is missing (CFR failure),
            False if all parameters are present.
        """
        if not intent.parameters:
            return False

        import re
        import ast

        for key, val in intent.parameters.items():
            # Check if this is a critical parameter
            key_lower = key.lower()
            is_critical = any(
                k in key_lower
                for k in [
                    "ip",
                    "address",
                    "mask",
                    "netmask",
                    "neighbor",
                    "as",
                    "area",
                    "vlan",
                    "remote",
                    "port",
                    "gateway",
                    "subnet",
                ]
            )
            if not is_critical:
                continue

            # Handle potential list of values (e.g., VLANs 10,20,30)
            if isinstance(val, list):
                vals = val
            elif isinstance(val, str) and val.startswith("[") and val.endswith("]"):
                try:
                    vals = ast.literal_eval(val)
                    if not isinstance(vals, list):
                        vals = [val]
                except:
                    vals = [val]
            else:
                vals = [val]

            for v in vals:
                val_str = str(v).strip()

                # Determine parameter type and check accordingly
                if "/" in val_str and val_str.split("/")[0].replace(".", "").isdigit():
                    # IP/CIDR parameter - pass FULL value including prefix
                    if not self._config_contains_ip(config, val_str):
                        return True
                elif any(c.isdigit() for c in val_str) and "." not in val_str:
                    # Numeric parameter (VLAN, AS, area, port) - check with keyword context
                    if not self._config_contains_value(config, key, val_str):
                        return True
                elif "." in val_str and self._is_ip_like(val_str):
                    # IP address parameter - pass full value
                    if not self._config_contains_ip(config, val_str):
                        return True

        return False

    def _is_ip_like(self, val: str) -> bool:
        """
        Check if a value looks like an IP address.

        Args:
            val: String value to check.

        Returns:
            True if value appears to be an IP address.
        """
        parts = val.replace("/", " ").split()
        if parts:
            first_part = parts[0]
            return all(part.isdigit() for part in first_part.split("."))
        return False

    def _config_contains_ip(self, config: str, ip_with_prefix: str) -> bool:
        """
        Check if config contains the given IP address with correct prefix/mask.

        Returns True only if IP is found with CORRECT prefix/mask.
        Tracks perfect matches vs near matches (IP with wrong mask).
        Handles Cisco ACL wildcard masks (0.0.0.255) vs subnet masks (255.255.255.0).

        Args:
            config: Configuration string to search.
            ip_with_prefix: IP address with optional prefix (e.g., "10.1.1.0/24").

        Returns:
            True if IP found with correct mask/prefix, False otherwise.
        """
        import re

        # Parse IP and prefix
        if "/" in ip_with_prefix:
            parts = ip_with_prefix.split("/")
            ip_base = parts[0]
            intent_prefix = parts[1]
        else:
            ip_base = ip_with_prefix
            intent_prefix = None

        # Find all IPs in config
        ip_pattern = r"\d+\.\d+\.\d+\.\d+"
        config_ips = re.findall(ip_pattern, config)

        # Check if IP exists at all
        if ip_base not in config_ips:
            return False

        # If no prefix specified, just check IP exists
        if not intent_prefix:
            return True

        # CIDR prefix provided - verify prefix/mask matches
        prefix_to_mask = {
            "0": "0.0.0.0",
            "8": "255.0.0.0",
            "16": "255.255.0.0",
            "24": "255.255.255.0",
            "25": "255.255.255.128",
            "26": "255.255.255.192",
            "27": "255.255.255.224",
            "28": "255.255.255.240",
            "29": "255.255.255.248",
            "30": "255.255.255.252",
            "31": "255.255.255.254",
            "32": "255.255.255.255",
        }

        # Reverse masks (Cisco wildcard style)
        prefix_to_wildcard = {
            "0": "255.255.255.255",
            "8": "0.255.255.255",
            "16": "0.0.255.255",
            "24": "0.0.0.255",
            "25": "0.0.0.127",
            "26": "0.0.0.63",
            "27": "0.0.0.31",
            "28": "0.0.0.15",
            "29": "0.0.0.7",
            "30": "0.0.0.3",
            "31": "0.0.0.1",
            "32": "0.0.0.0",
        }

        intent_mask = prefix_to_mask.get(intent_prefix)
        intent_wildcard = prefix_to_wildcard.get(intent_prefix)

        perfect_match = False
        near_match = False

        # Check if this is an ACL context (has access-list related keywords)
        is_acl_context = "access-list" in config.lower() or "acl" in config.lower()

        # Find all lines containing the IP
        for line in config.split("\n"):
            if ip_base not in line:
                continue

            # Check for CIDR notation (e.g., 10.1.1.1/24)
            cidr_match = re.search(rf"{re.escape(ip_base)}/(\d+)", line)
            if cidr_match:
                if cidr_match.group(1) == intent_prefix:
                    perfect_match = True
                    break
                else:
                    near_match = True
                    continue

            # Check for mask notation (e.g., 255.255.255.0)
            if intent_mask and intent_mask in line:
                perfect_match = True
                break

            # Check for wildcard notation (e.g., 0.0.0.255) - used in Cisco ACLs
            if intent_wildcard and intent_wildcard in line:
                perfect_match = True
                break

            # ACL-specific: Check for wildcard mask on same line
            # In Cisco ACLs: "10.0.0.0 0.0.0.255" means 10.0.0.0/24
            if is_acl_context:
                # Find wildcard mask on this line
                wildcard_match = re.search(
                    r"(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", line
                )
                if wildcard_match:
                    potential_wildcard = wildcard_match.group(2)
                    # Check if this wildcard matches the expected /24 (or other prefix)
                    if intent_wildcard and potential_wildcard == intent_wildcard:
                        perfect_match = True
                        break
                    elif potential_wildcard in prefix_to_wildcard.values():
                        # Found a wildcard but different from expected
                        near_match = True
                        continue

            # IP found but no mask info - might be correct
            # Check if line has ANY mask (could be wrong one)
            has_mask = any(m in line for m in prefix_to_mask.values())
            has_wildcard = any(w in line for w in prefix_to_wildcard.values())
            has_cidr = "/2" in line or "/1" in line
            if has_mask or has_cidr or has_wildcard:
                near_match = True  # IP found but mask might be wrong
            else:
                perfect_match = True  # IP found in line without mask requirement

        # Return True only if we found a perfect match
        # If only near matches (IP with wrong mask), return False (CFR failure)
        return perfect_match

    def _config_contains_value(self, config: str, param_key: str, value: str) -> bool:
        """
        Check if config contains the given numeric value with keyword context.

        E.g., for 'vlan 100', check for 'vlan' followed by '100'.
        This ensures values aren't accidentally matched in wrong contexts.

        Args:
            config: Configuration string to search.
            param_key: Parameter key (e.g., "vlan", "area").
            value: Value to find (e.g., "100").

        Returns:
            True if value found with correct keyword context.
        """
        import re

        # Define keyword patterns for common numeric parameters
        keyword_patterns = {
            "vlan": r"vlan\s+",
            "area": r"area\s+",
            "as": r"(?:remote-as|autonomous-system|as)\s+",
            "neighbor": r"neighbor\s+",
            "remote": r"remote-as\s+",
            "port": r"(?:eq|port)\s+",
            "mtu": r"mtu\s+",
            "priority": r"priority\s+",
            "cost": r"cost\s+",
            "bandwidth": r"bandwidth\s+",
            "hello": r"hello-interval\s+",
        }

        # Check if param_key has a known keyword pattern
        key_lower = param_key.lower()
        for kw, pattern in keyword_patterns.items():
            if kw in key_lower:
                # Search for keyword followed by the value
                combined_pattern = f"{pattern}{re.escape(value)}(\\s|$)"
                if re.search(combined_pattern, config, re.IGNORECASE):
                    return True
                return False

        # Fallback: if no keyword pattern matches, check standalone value
        # But be more strict - look for value at word boundaries
        standalone_pattern = f"(?<![\\w/]){re.escape(value)}(?![\\w/])"
        return bool(re.search(standalone_pattern, config))

    def _normalize_for_comparison(self, value: str) -> str:
        """
        Normalize values for comparison (e.g., /24 -> 255.255.255.0).

        Args:
            value: Value string to normalize.

        Returns:
            Normalized value string.
        """
        import re

        # Handle CIDR notation
        cidr_map = {
            "0": "0.0.0.0",
            "8": "255.0.0.0",
            "16": "255.255.0.0",
            "24": "255.255.255.0",
            "25": "255.255.255.128",
            "26": "255.255.255.192",
            "27": "255.255.255.224",
            "28": "255.255.255.240",
            "29": "255.255.255.248",
            "30": "255.255.255.252",
            "31": "255.255.255.254",
            "32": "255.255.255.255",
        }
        value = str(value).strip()
        if "/" in value:
            parts = value.split("/")
            ip = parts[0]
            prefix = parts[1].split()[0] if " " in parts[1] else parts[1]
            if prefix in cidr_map:
                value = f"{ip} {cidr_map[prefix]}"
        return value.lower().strip()

    def _generate_summary_table(self, results: List[Dict]):
        """
        Generate and print summary table of evaluation results.

        Computes metrics for both vanilla and RAG modes:
        - Syntactic Validity: % passing Batfish validation
        - Hallucination Rate: % with detected hallucinations
        - CFR Failure Rate: % missing critical parameters
        - CFR Faithfulness: % with all parameters present
        - Avg Latency: Average generation time

        Args:
            results: List of evaluation result dictionaries.
        """
        summary = []
        for mode in ["vanilla", "rag_nettwin"]:
            # Fix: RAG mode status is nested in 'validation', Vanilla is top-level.
            # We filter for anything that isn't an explicit ERROR status string.
            mode_data = []
            for r in results:
                if (
                    mode in r
                    and isinstance(r[mode], dict)
                    and r[mode].get("status") != "ERROR"
                ):
                    mode_data.append(r[mode])

            if not mode_data:
                continue

            # Syntactic Validity: Count PASS or WARNING. If SKIPPED, we mark as N/A or 0.
            pass_count = 0
            for d in mode_data:
                # Check both top-level (vanilla) and nested (rag) validation status
                status = d.get("status")
                if not status and "validation" in d:
                    status = d["validation"].get("status")

                if status in ["PASS", "WARNING"]:
                    pass_count += 1

            cfr_count = sum(1 for d in mode_data if d.get("cfr_failure", False))

            if mode == "vanilla":
                hal_count = sum(
                    1
                    for d in mode_data
                    if d.get("hallucination", {}).get("is_hallucinated")
                )
            else:
                hal_count = sum(
                    1
                    for d in mode_data
                    if any(
                        h.get("is_hallucinated") for h in d.get("hallucinations", [])
                    )
                )

            summary.append(
                {
                    "Mode": mode,
                    "Syntactic Validity": f"{(pass_count / len(mode_data)) * 100:.1f}%",
                    "Hallucination Rate": f"{(hal_count / len(mode_data)) * 100:.1f}%",
                    "CFR Failure Rate": f"{(cfr_count / len(mode_data)) * 100:.1f}%",
                    "CFR Faithfulness": f"{((len(mode_data) - cfr_count) / len(mode_data)) * 100:.1f}%",
                    "Avg Latency": f"{sum(d.get('latency', 0) for d in mode_data) / len(mode_data):.2f}s"
                    if mode == "rag_nettwin"
                    else "N/A",
                }
            )

        print("\n UPDATED RESEARCH METRICS (RAG-NetTwin v3)")
        print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RAG-NetTwin Paper Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # RAG-Only mode (default, skips vanilla LLM)
  uv run python run_paper_eval.py

  # Run with vanilla LLM comparison
  uv run python run_paper_eval.py --run-vanilla

  # Use only cached results (no new API calls)
  uv run python run_paper_eval.py --cache-only

  # Clear caches and run fresh
  uv run python run_paper_eval.py --clear-cache

  # Run vanilla comparison with cache-only mode
  uv run python run_paper_eval.py --run-vanilla --cache-only
""",
    )
    parser.add_argument(
        "--run-vanilla",
        action="store_true",
        help="Also run vanilla LLM baseline (default: skip vanilla)",
    )
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear all caches before running"
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use only cached results, no new API calls",
    )
    args = parser.parse_args()

    # Clear caches if requested
    if args.clear_cache:
        for cache_file in [VANILLA_CACHE_FILE, RAG_CACHE_FILE]:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                print(f"Cleared cache: {cache_file}")
        print("Starting fresh evaluation...")

    # Run evaluation
    evaluator = PaperQualityEvaluator(
        run_vanilla=args.run_vanilla, cache_only=args.cache_only
    )
    evaluator.run_full_eval()
