import json
import time
import os
import argparse
import random
import hashlib
import threading
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any, cast
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
)
from rich.panel import Panel

# Add src to path for imports

from src.parser.intent_parser import IntentParser
from src.rag.config_generator import ConfigGenerator, CONFIG_GENERATOR_VERSION
from src.rag.parameter_normalizer import ParameterNormalizer
from src.validation.batfish_validator import BatfishValidator
from src.validation.gns3_validator import GNS3Validator
from src.llm import LLMProvider
from src.config import settings
from src.evaluation.hallucination_detector import HallucinationDetector
from src.utils import setup_logger, TokenCounter
from src.evaluation.cache_manager import CacheManager
from src.evaluation.cfr_checker import CFRChecker
from src.evaluation.stats_reporter import StatsReporter

logger = setup_logger("PaperEval")

VANILLA_CACHE_FILE = "vanilla_cache.json"
RAG_CACHE_FILE = "rag_cache.json"


class PaperQualityEvaluator:
    """
    Optimized high-scale evaluation script for RAG-NetTwin.
    """

    def __init__(
        self,
        run_vanilla: bool = False,
        cache_only: bool = False,
        run_gns3: bool = False,
        re_validate: bool = False,
        interactive: bool = False,
        parser: Optional[IntentParser] = None,
        generator: Optional[ConfigGenerator] = None,
        validator: Optional[BatfishValidator] = None,
        hallucination_detector: Optional[HallucinationDetector] = None,
        token_counter: Optional[TokenCounter] = None,
        evaluation_mode: str = "strict",
    ):
        self.console = Console()
        self.parser = parser or IntentParser()
        self.generator = generator or ConfigGenerator()
        self.validator = validator or BatfishValidator()
        self.hallucination_detector = hallucination_detector or HallucinationDetector()
        self.token_counter = token_counter or TokenCounter()
        self.vanilla_llm = LLMProvider.get_llm(temperature=0.0) if run_vanilla else None
        self.run_vanilla = run_vanilla
        self.cache_only = cache_only
        self.run_gns3 = run_gns3
        self.re_validate = re_validate
        self.interactive = interactive
        self.evaluation_mode = evaluation_mode

        self.cache_manager = CacheManager()
        self.cfr_checker = CFRChecker()
        self.stats_reporter = StatsReporter()
        self.evaluation_lock = threading.Lock()
        self.gns3_lock = threading.Lock()

        self.gns3 = None
        if self.run_gns3 and not self.cache_only:
            self.gns3 = GNS3Validator()
            if not self.gns3.connected:
                logger.warning(
                    "GNS3 requested but server not connected. Tier 3 metrics will be skipped."
                )
                self.run_gns3 = False

        self.vanilla_cache = self.cache_manager.load_cache(VANILLA_CACHE_FILE)
        self.rag_cache = self.cache_manager.load_cache(RAG_CACHE_FILE)

        os.makedirs("results", exist_ok=True)
        logger.info(f"Loaded vanilla cache: {len(self.vanilla_cache)} items")
        logger.info(f"Loaded RAG cache: {len(self.rag_cache)} items")

    def get_intent_key(self, intent) -> str:
        return intent.original_text if hasattr(intent, "original_text") else str(intent)

    def get_test_intents(self) -> List[str]:
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
            "Configure IPv6 address 2001:db8:acad::1/64 on interface GigabitEthernet0/2",
            "Set up OSPFv3 area 0 for IPv6 on Cisco IOS-XE",
            "Configure a NAT overload (PAT) for subnet 192.168.10.0/24 on interface Gig0/1",
            "Create a site-to-site VPN between Cisco (1.1.1.1) and Juniper (2.2.2.2) with PSK 'SecretKey'",
            "Set up a QoS policy to prioritize OSPF traffic (CS6) on Cisco",
            "Configure an VRRP group 10 with virtual IP 10.1.1.254 on interface ge-0/0/0 for Juniper",
            "Enable DHCP snooping for VLANs 10,20 on a Cisco Catalyst switch",
            "Configure a prefix-list to permit only 10.0.0.0/8 and its subnets on Juniper",
            "Set up an LACP etherchannel (Group 1) using Gig1/0/1 and Gig1/0/2 on Cisco",
            "Configure NetFlow (IPFIX) to export to 10.1.1.50 on port 2055 from Cisco",
            "Restrict console access with an execution timeout of 5 minutes on Juniper",
            "Set up a BGP route reflector with neighbor 172.16.1.1 on Cisco",
        ]

    def run_full_eval(self, retrieval_mode: str = "tiered"):
        logger.info(
            f"Pre-flight check: Verifying Batfish connectivity (Mode: {retrieval_mode})..."
        )
        try:
            if not self.validator.session:
                raise ConnectionError("Batfish session not initialized.")
            self.validator.session.list_networks()
            logger.info("Batfish detected and responsive.")
        except Exception as e:
            logger.error(f"Batfish pre-flight failed: {e}")
            if not self.cache_only:
                return

        scenarios = self.get_test_intents()
        all_results = []
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        metadata = {
            "timestamp": timestamp,
            "llm_provider": settings.llm_provider,
            "embedding_model": settings.embedding_model_name,
            "retrieval_mode": retrieval_mode,
            "run_vanilla": self.run_vanilla,
            "cache_only": self.cache_only,
        }

        logger.info(f"Phase 1: Batch parsing {len(scenarios)} intents...")
        parsed_intents = self.parser.parse_batch(scenarios)

        logger.info(
            f"Phase 2: Evaluating in parallel... (Retrieval Mode: {retrieval_mode})"
        )
        all_results_map = {}

        # Parallelize the evaluation loop
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Evaluating ({retrieval_mode})", total=len(parsed_intents)
            )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future_to_intent = {
                    executor.submit(
                        self.evaluate_intent, intent, retrieval_mode=retrieval_mode
                    ): (i, intent)
                    for i, intent in enumerate(parsed_intents)
                }

                for future in as_completed(future_to_intent):
                    idx, intent = future_to_intent[future]
                    try:
                        res = future.result()
                        if res:
                            # Real-time failure reporting
                            rag_res = res.get("rag_nettwin", {})
                            status = rag_res.get("status")
                            if status in ["ERROR", "FAIL", "REJECT_FOR_MANUAL_REVIEW"]:
                                self._print_failure_report(idx, intent, res)

                            all_results_map[idx] = res
                    except Exception as e:
                        err_str = str(e)
                        if "429" in err_str or "rate_limit" in err_str.lower():
                            original_text = intent.original_text or "Unknown"
                            logger.error(
                                f"\n🛑 RATE LIMIT EXCEEDED at Intent #{idx + 1}: {original_text[:50]}..."
                            )
                            logger.error(f"Error Details: {err_str}")
                        else:
                            self._print_failure_report(
                                idx,
                                intent,
                                {"rag_nettwin": {"status": "ERROR", "error": err_str}},
                            )

                    progress.update(task, advance=1)

        # Sort results back into original order
        all_results = [
            all_results_map[i]
            for i in range(len(parsed_intents))
            if i in all_results_map
        ]

        os.makedirs("results/history", exist_ok=True)
        report = {"metadata": metadata, "results": all_results}
        latest_file = f"results/paper_evaluation_{retrieval_mode}_latest.json"
        with open(latest_file, "w") as f:
            json.dump(report, f, indent=2)

        history_file = f"results/history/report_{retrieval_mode}_{timestamp}.json"
        with open(history_file, "w") as f:
            json.dump(report, f, indent=2)

        if not self.cache_only:
            self.cache_manager.save_cache(VANILLA_CACHE_FILE, self.vanilla_cache)
            self.cache_manager.save_cache(RAG_CACHE_FILE, self.rag_cache)

        self.stats_reporter.generate_summary_table(all_results, retrieval_mode)
        self._print_final_failure_summary(all_results)

    def _get_authorized_citations(self) -> List[str]:
        """
        Scans graph_tmp for actual documentation filenames.
        """
        import glob

        files = glob.glob("graph_tmp/*.txt")
        names = [Path(f).stem for f in files]
        return names

    def evaluate_intent(self, intent, retrieval_mode: str = "tiered"):
        intent_key = self.get_intent_key(intent)
        results = {
            "scenario": intent.original_text,
            "parsed_intent": intent.model_dump(),
        }

        authorized_citations = self._get_authorized_citations()

        # --- RAG Mode ---
        cache_key = f"{CONFIG_GENERATOR_VERSION}:{retrieval_mode}:{intent_key}"
        use_live_llm = os.getenv("USE_LIVE_LLM") == "True" or getattr(
            settings, "use_live_llm", False
        )
        with self.evaluation_lock:
            if use_live_llm:
                cached_rag = None
            else:
                cached_rag = self.cache_manager.get(self.rag_cache, cache_key)

        # [INTERACTIVE] Check for retrying failed entries
        if (
            cached_rag
            and self.interactive
            and cached_rag.get("status")
            not in ["PASS", "WARNING", "REJECT_FOR_MANUAL_REVIEW"]
        ):
            print(f"\n[INTERACTIVE] Cached failure for: {intent_key[:70]}...")
            choice = input("  Retry AI generation? (y/n): ").strip().lower()
            if choice == "y":
                cached_rag = None

        if cached_rag:
            # [RE-VALIDATE] If requested, re-run local validation on cached config
            if self.re_validate:
                logger.info(f"Re-validating cached config: {intent_key[:20]}...")
                device_configs = cached_rag.get("configs", {})
                if device_configs:
                    try:
                        val_report = self.validator.validate(device_configs, intent)
                        cached_rag["status"] = val_report.get("status")
                        cached_rag["issues"] = val_report.get("issues", [])
                        # Update cache with new validation status
                        with self.evaluation_lock:
                            self.cache_manager.set(
                                self.rag_cache,
                                cache_key,
                                cached_rag,
                                mode=retrieval_mode,
                            )
                    except Exception as e:
                        logger.error(f"Re-validation failed: {e}")

            # RE-RUN GNS3 even if cached (to verify environment stability)
            if self.run_gns3 and self.gns3 and not self.cache_only:
                logger.info(f"RAG cache hit - Re-running GNS3: {intent_key[:20]}...")
                device_configs = cached_rag.get("configs", {})

                # Apply post-processing even to cached configs to benefit from latest regex improvements
                processed_configs = {}
                for dev_name, config in device_configs.items():
                    vendor = "cisco"  # Default for normalization if unknown
                    processed_configs[dev_name] = (
                        ParameterNormalizer.post_process_config(config, vendor=vendor)
                    )

                batfish_failed = cached_rag.get("status") in [
                    "ERROR",
                    "FAIL",
                    "REJECT_FOR_MANUAL_REVIEW",
                ]
                should_run_gns3 = True
                if batfish_failed and self.evaluation_mode == "strict":
                    logger.warning(
                        "Short-circuiting GNS3 validation for cached entry due to Batfish failure in strict mode."
                    )
                    cached_rag["functional_status"] = "SKIPPED_FAIL"
                    cached_rag["functional_errors"] = [
                        "Skipped GNS3 validation due to Batfish failure in strict mode."
                    ]
                    should_run_gns3 = False
                    with self.evaluation_lock:
                        self.cache_manager.set(
                            self.rag_cache,
                            cache_key,
                            cached_rag,
                            mode=retrieval_mode,
                        )

                if should_run_gns3 and processed_configs:
                    try:
                        with self.gns3_lock:
                            g_res = self.gns3.validate(processed_configs, intent)
                            cached_rag["functional_status"] = g_res.get(
                                "status", "FAIL"
                            )
                            cached_rag["functional_errors"] = [
                                g_res.get("summary")
                                or g_res.get("error")
                                or "GNS3 node initialization failed."
                            ]
                            cached_rag["car"] = g_res.get("car", 0.0)
                            cached_rag["telnet_logs"] = g_res.get("telnet_logs", {})

                            # Update cache with functional results
                            with self.evaluation_lock:
                                self.cache_manager.set(
                                    self.rag_cache,
                                    cache_key,
                                    cached_rag,
                                    mode=retrieval_mode,
                                )
                    except Exception as e:
                        logger.error(f"GNS3 verification failed for cached entry: {e}")

            results["rag_nettwin"] = cached_rag
            configs = cached_rag.get("configs", {})
            all_hal_reports = []
            all_sources = []
            for s_list in cached_rag.get("retrieved_sources", []):
                if isinstance(s_list, list):
                    all_sources.extend(s_list)

            # Map valid source IDs (Flatten for robustness in cached runs)
            flat_valid_ids = []
            for v_list in cached_rag.get("valid_source_ids", []):
                if isinstance(v_list, list):
                    flat_valid_ids.extend(v_list)
                elif isinstance(v_list, str):
                    flat_valid_ids.append(v_list)

            all_texts = [t for t in cached_rag.get("retrieved_texts", []) if t]

            for i, (dev_name, config_text) in enumerate(configs.items()):
                if dev_name and dev_name.startswith("_"):
                    continue

                hal_report = self.hallucination_detector.detect(
                    config_text,
                    all_sources,
                    flat_valid_ids,  # Use flattened list for cached safety
                    retrieved_texts=all_texts,
                    intent_context=intent.original_text,
                    intent_params=intent.parameters,
                    master_plan=cached_rag.get("master_plan"),
                    authorized_citations=authorized_citations,
                )
                all_hal_reports.append(hal_report.model_dump())
            results["rag_nettwin"]["hallucinations"] = all_hal_reports
            aggregate_config = "\n".join(configs.values())
            results["rag_nettwin"]["cfr_failure"] = self.cfr_checker.check(
                intent, aggregate_config
            )
            logger.info(f"RAG cache hit (re-evaluated): {intent_key[:20]}...")
        elif self.cache_only:
            results["rag_nettwin"] = {
                "status": "ERROR",
                "error": "Not in cache (cache-only mode)",
            }
        else:
            try:
                start_time = time.time()
                rag_output = self.generator.generate(
                    intent, retrieval_mode=retrieval_mode
                )
                latency = time.time() - start_time
                results["rag_sanity_check"] = rag_output.get("_sanity_check")
                device_configs = {
                    k: v["config"]
                    for k, v in rag_output.items()
                    if k is None or not k.startswith("_")
                }
                if not device_configs:
                    raise ValueError("No device configurations generated.")

                val_report = self.validator.validate(device_configs, intent)
                # Deep Trace: Aggregate RAG and Functional logs
                deep_trace = rag_output.pop("_trace", {})
                master_plan = deep_trace.get("master_plan")

                # Force re-run of GNS3 if run_gns3 is enabled, even if RAG was cached
                # (handled by not having 'eval_res' yet in this block)

                all_hal_reports = []
                for dev_name, dev_data in rag_output.items():
                    if dev_name and dev_name.startswith("_"):
                        continue
                    hal_report = self.hallucination_detector.detect(
                        dev_data["config"],
                        dev_data.get("retrieved_sources", []),
                        dev_data.get("valid_source_ids", []),
                        retrieved_texts=[dev_data.get("grounding_context", "")],
                        intent_context=intent.original_text,
                        intent_params=intent.parameters,
                        master_plan=master_plan,
                        authorized_citations=authorized_citations,
                    )
                    all_hal_reports.append(hal_report.model_dump())

                aggregate_config = "\n".join(device_configs.values())
                cfr_failure = self.cfr_checker.check(intent, aggregate_config)

                functional_status = "SKIPPED"
                gns3_car = 0.0
                is_multi_vendor = False
                functional_errors = []

                batfish_failed = val_report.get("status") in [
                    "ERROR",
                    "FAIL",
                    "REJECT_FOR_MANUAL_REVIEW",
                ]
                should_run_gns3 = bool(self.run_gns3 and self.gns3)

                if (
                    should_run_gns3
                    and batfish_failed
                    and self.evaluation_mode == "strict"
                ):
                    logger.warning(
                        f"Short-circuiting GNS3 validation due to Batfish failure in strict mode ({val_report.get('status')})."
                    )
                    functional_status = "SKIPPED_FAIL"
                    functional_errors = [
                        "Skipped GNS3 validation due to Batfish failure in strict mode."
                    ]
                    should_run_gns3 = False

                if should_run_gns3 and self.gns3 is not None:
                    try:
                        with self.gns3_lock:
                            g_res = self.gns3.validate(device_configs, intent)
                            gns3_car = g_res.get("car", 0.0)
                            is_multi_vendor = g_res.get("is_multi_vendor", False)

                            if g_res.get("status") == "PASS":
                                v_cmds = {
                                    k: v.get("verification_commands", [])
                                    for k, v in rag_output.items()
                                    if k is None or not k.startswith("_")
                                }
                                v_res = self.gns3.verify_functional(
                                    g_res.get("nodes", {}), v_cmds
                                )
                                has_functional_error = False
                                functional_errors = []
                                for dev_name, cmd_outputs in v_res.items():
                                    outputs_to_check = (
                                        list(cmd_outputs.values())
                                        if isinstance(cmd_outputs, dict)
                                        else cmd_outputs
                                    )

                                    # Process raw outputs from verify_functional
                                    if isinstance(outputs_to_check, list):
                                        for entry in outputs_to_check:
                                            out = (
                                                entry.get("output", "")
                                                if isinstance(entry, dict)
                                                else str(entry)
                                            )
                                            if (
                                                "ERROR:" in out
                                                or "TIMEOUT:" in out
                                                or "Invalid input" in out
                                            ):
                                                has_functional_error = True
                                                functional_errors.append(
                                                    f"{dev_name}: {out[:100]}..."
                                                )
                                                break
                                    if has_functional_error:
                                        break

                                functional_status = (
                                    "PASS" if not has_functional_error else "FAIL"
                                )
                                if has_functional_error:
                                    functional_errors = (
                                        functional_errors  # Already populated above
                                    )
                            else:
                                functional_status = g_res.get("status", "FAIL")
                                # Fallback chain for summary: summary -> error -> default
                                functional_errors = [
                                    g_res.get("summary")
                                    or g_res.get("error")
                                    or "GNS3 node initialization failed."
                                ]
                    except Exception as ge:
                        logger.error(f"GNS3 validation failed: {ge}")
                        functional_status = "ERROR"
                        functional_errors = [str(ge)]

                if self.run_gns3 and self.gns3 and "g_res" in locals():
                    deep_trace["telnet_logs"] = g_res.get("telnet_logs", {})

                eval_res = {
                    "scenario": intent.original_text,
                    "configs": device_configs,
                    "status": val_report.get("status"),
                    "error": val_report.get("error") or val_report.get("message"),
                    "issues": val_report.get("issues", []),
                    "functional_status": functional_status,
                    "functional_errors": functional_errors
                    if "functional_errors" in locals()
                    else [],
                    "car": gns3_car,
                    "is_multi_vendor": is_multi_vendor,
                    "master_plan": master_plan,
                    "latency": latency,
                    "hallucinations": all_hal_reports,
                    "cfr_failure": cfr_failure,
                    "retrieved_sources": [
                        v.get("retrieved_sources", [])
                        for k, v in rag_output.items()
                        if k is None or not k.startswith("_")
                    ],
                    "valid_source_ids": [
                        v.get("valid_source_ids", [])
                        for k, v in rag_output.items()
                        if k is None or not k.startswith("_")
                    ],
                    "retrieved_texts": [
                        v.get("grounding_context", "")
                        for k, v in rag_output.items()
                        if k is None or not k.startswith("_")
                    ],
                }

                # Save trace to disk and link it
                trace_path = self._save_deep_trace(intent, retrieval_mode, deep_trace)
                eval_res["deep_trace_file"] = trace_path

                results["rag_nettwin"] = eval_res
                with self.evaluation_lock:
                    self.cache_manager.set(
                        self.rag_cache, cache_key, eval_res, mode=retrieval_mode
                    )
            except Exception as e:
                logger.error(f"RAG Evaluation failed: {e}")
                results["rag_nettwin"] = {"status": "ERROR", "error": str(e)}

        # --- Vanilla LLM ---
        if self.run_vanilla:
            with self.evaluation_lock:
                if use_live_llm:
                    cached_vanilla = None
                else:
                    cached_vanilla = self.cache_manager.get(
                        self.vanilla_cache, intent_key
                    )

            # [INTERACTIVE] Check for retrying failed entries
            if (
                cached_vanilla
                and self.interactive
                and cached_vanilla.get("status")
                not in ["PASS", "WARNING", "REJECT_FOR_MANUAL_REVIEW"]
            ):
                print(
                    f"\n[INTERACTIVE] Cached vanilla failure for: {intent_key[:70]}..."
                )
                choice = input("  Retry AI generation? (y/n): ").strip().lower()
                if choice == "y":
                    cached_vanilla = None

            if cached_vanilla:
                # [RE-VALIDATE]
                if self.re_validate:
                    logger.info(
                        f"Re-validating cached vanilla config: {intent_key[:20]}..."
                    )
                    vanilla_cfg = cached_vanilla.get("config", "")
                    if vanilla_cfg:
                        try:
                            validation = self.validator.validate(
                                {"Vanilla-Router": vanilla_cfg}
                            )
                            cached_vanilla["status"] = validation["status"]
                            cached_vanilla["issues"] = validation.get("issues", [])
                            with self.evaluation_lock:
                                self.cache_manager.set(
                                    self.vanilla_cache,
                                    intent_key,
                                    cached_vanilla,
                                    mode="vanilla",
                                )
                        except Exception as e:
                            logger.error(f"Vanilla re-validation failed: {e}")

                results["vanilla"] = cached_vanilla
                logger.info(f"Vanilla cache hit: {intent_key[:20]}...")
            elif self.cache_only:
                results["vanilla"] = {
                    "status": "ERROR",
                    "error": "Not in cache (cache-only mode)",
                }
            else:
                try:
                    vanilla_cfg = self._generate_vanilla(intent.original_text)
                    validation = self.validator.validate(
                        {"Vanilla-Router": vanilla_cfg}
                    )
                    functional_status = "SKIPPED"

                    batfish_failed = validation.get("status") in [
                        "ERROR",
                        "FAIL",
                        "REJECT_FOR_MANUAL_REVIEW",
                    ]
                    should_run_gns3 = bool(self.run_gns3 and self.gns3)

                    if (
                        should_run_gns3
                        and batfish_failed
                        and self.evaluation_mode == "strict"
                    ):
                        logger.warning(
                            f"Short-circuiting Vanilla GNS3 validation due to Batfish failure in strict mode ({validation.get('status')})."
                        )
                        functional_status = "SKIPPED_FAIL"
                        should_run_gns3 = False

                    if should_run_gns3 and self.gns3 is not None:
                        try:
                            v_cmds = {
                                "Vanilla-Router": [
                                    "show ip interface brief",
                                    "show running-config",
                                ]
                            }
                            g_res = self.gns3.validate(
                                {"Vanilla-Router": vanilla_cfg}, intent
                            )
                            if g_res.get("status") == "PASS":
                                v_res = self.gns3.verify_functional(
                                    g_res.get("nodes", {}), v_cmds
                                )
                                has_err = any(
                                    out and str(out).startswith("ERROR:")
                                    for dev in v_res.values()
                                    for out in dev.values()
                                )
                                functional_status = "PASS" if not has_err else "FAIL"
                            else:
                                functional_status = "FAIL"
                        except Exception as ge:
                            logger.error(f"GNS3 Vanilla validation failed: {ge}")
                            functional_status = "ERROR"

                    vanilla_result = {
                        "config": vanilla_cfg,
                        "status": validation["status"],
                        "issues": validation.get("issues", []),
                        "functional_status": functional_status,
                        "cfr_failure": self.cfr_checker.check(intent, vanilla_cfg),
                        "hallucination": self.hallucination_detector.detect(
                            vanilla_cfg, [], [], intent_context=intent.original_text
                        ).model_dump(),
                    }
                    results["vanilla"] = vanilla_result
                    with self.evaluation_lock:
                        self.cache_manager.set(
                            self.vanilla_cache,
                            intent_key,
                            vanilla_result,
                            mode="vanilla",
                        )
                except Exception as e:
                    results["vanilla"] = {"status": "ERROR", "error": str(e)}
        return results

    def _generate_vanilla(self, scenario: str) -> str:
        from langchain_core.prompts import ChatPromptTemplate

        # Try to extract vendor from scenario to help the baseline
        vendor_hint = ""
        if "cisco" in scenario.lower():
            vendor_hint = "Cisco IOS"
        elif "juniper" in scenario.lower() or "junos" in scenario.lower():
            vendor_hint = "Juniper Junos"

        prompt = ChatPromptTemplate.from_template(
            "Task: Generate {vendor_hint} CLI for {request}. "
            "Output ONLY the raw commands. NO prose. "
            "If no vendor is specified, provide Cisco IOS. CLI:"
        )
        if not self.vanilla_llm:
            return "Vanilla LLM not initialized"

        chain = prompt | self.vanilla_llm
        response = chain.invoke(
            {"request": scenario, "vendor_hint": vendor_hint or "Cisco/Juniper"}
        )
        return cast(str, response.content)

    def _save_deep_trace(self, intent, mode: str, trace_data: Dict[str, Any]) -> str:
        """
        Saves detailed execution trace to a timestamped JSON file.
        """
        trace_dir = Path("results/traces")
        trace_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        intent_id = hashlib.md5(intent.original_text.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{mode}_{intent_id}.json"
        filepath = trace_dir / filename

        with open(filepath, "w") as f:
            json.dump(trace_data, f, indent=2)

        return str(filepath)

    def _print_failure_report(self, idx: int, intent: Any, res: Dict[str, Any]):
        """
        Prints a detailed failure report to the console using rich.
        """
        rag_res = res.get("rag_nettwin", {})
        status = rag_res.get("status", "UNKNOWN")
        intent_text = (
            intent.original_text if hasattr(intent, "original_text") else str(intent)
        )

        # Determine color and icon
        color = "red"
        icon = "❌"
        if status == "REJECT_FOR_MANUAL_REVIEW":
            color = "yellow"
            icon = "⚠️"
        elif status == "FAIL":
            color = "orange3"
            icon = "🛑"

        content = []
        content.append(f"[bold {color}]Intent:[/bold {color}] {intent_text}")
        content.append(f"[bold {color}]Status:[/bold {color}] {status}")

        if "error" in rag_res and rag_res["error"]:
            content.append(f"[bold red]Error:[/bold red] {rag_res['error']}")

        if "issues" in rag_res and rag_res["issues"]:
            content.append("\n[bold]Issues Found (Tier 1):[/bold]")
            for issue in rag_res["issues"]:
                content.append(
                    f"  • [[bold cyan]{issue.get('type')}[/bold cyan]] {issue.get('details')}"
                )

        if rag_res.get("functional_status") in ["FAIL", "ERROR"]:
            content.append(
                f"\n[bold]Functional Status (Tier 3):[/bold] [bold red]{rag_res.get('functional_status')}[/bold red]"
            )
            if "functional_errors" in rag_res:
                for f_err in rag_res["functional_errors"]:
                    content.append(f"  • {f_err}")

        if "configs" in rag_res:
            content.append("\n[bold]Generated Configs (Preview):[/bold]")
            retrieved_sources = rag_res.get("retrieved_sources", [])
            for i, (dev, cfg) in enumerate(rag_res["configs"].items()):
                snippet = cfg[:200] + "..." if len(cfg) > 200 else cfg
                content.append(f"[underline]{dev}:[/underline]\n[dim]{snippet}[/dim]")
                if i < len(retrieved_sources) and retrieved_sources[i]:
                    sources = ", ".join(retrieved_sources[i])
                    content.append(
                        f"[italic]🔗 Citations:[/italic] [blue]{sources}[/blue]"
                    )

        panel = Panel(
            "\n".join(content),
            title=f"{icon} [bold {color}]FAILURE at Intent #{idx + 1}[/bold {color}]",
            border_style=color,
            expand=False,
        )
        self.console.print(panel)

    def _print_final_failure_summary(self, results: List[Dict[str, Any]]):
        """
        Groups and prints all failures from the evaluation run using rich tables.
        """
        batfish_issues = {}  # type: Dict[str, List[str]]
        gns3_issues = []
        hallucination_issues: Dict[str, List[str]] = {
            "Invalid citations": [],
            "Ungrounded commands": [],
            "Placeholders": [],
            "Unauthorized parameters": [],
        }

        for res in results:
            scenario = res.get("scenario", "Unknown")
            rag = res.get("rag_nettwin", {})

            # Batfish issues
            for issue in rag.get("issues", []):
                i_type = issue.get("type", "UNKNOWN")
                details = issue.get("details", "")
                # Normalize details slightly to group similar errors
                norm_details = (
                    details.split(" at line:")[0] if " at line:" in details else details
                )
                key = f"[[bold cyan]{i_type}[/bold cyan]] {norm_details}"
                if key not in batfish_issues:
                    batfish_issues[key] = []
                batfish_issues[key].append(scenario)

            # GNS3 issues
            if rag.get("functional_status") in ["FAIL", "ERROR"]:
                for f_err in rag.get("functional_errors", []):
                    gns3_issues.append(f"[italic]{scenario}[/italic]\n{f_err}")

            # Hallucination issues
            for hal in rag.get("hallucinations", []):
                if hal.get("is_hallucinated"):
                    reason = hal.get("reason", "")
                    if "Invalid citations" in reason:
                        hallucination_issues["Invalid citations"].append(
                            f"[italic]{scenario}[/italic]\n{hal.get('invalid_citations')}"
                        )
                    if "Ungrounded commands" in reason:
                        hallucination_issues["Ungrounded commands"].append(
                            f"[italic]{scenario}[/italic]\n{hal.get('ungrounded_commands')}"
                        )
                    if "Placeholders" in reason:
                        hallucination_issues["Placeholders"].append(
                            f"[italic]{scenario}[/italic]\n{hal.get('suspicious_commands')}"
                        )
                    if "Unauthorized parameters" in reason:
                        hallucination_issues["Unauthorized parameters"].append(
                            f"[italic]{scenario}[/italic]\n{hal.get('unauthorized_parameters')}"
                        )

        self.console.print("\n")

        # 1. Batfish Table
        if batfish_issues:
            table = Table(
                title="[bold red]TIER 1: Batfish Static Analysis Failures[/bold red]",
                show_header=True,
                header_style="bold red",
            )
            table.add_column("Issue Pattern", style="white")
            table.add_column("Affected Scenarios (First 3)", style="dim")
            for issue_key, scenarios in batfish_issues.items():
                unique_scenarios = list(set(scenarios))
                preview = "\n".join([f"• {s[:50]}..." for s in unique_scenarios[:3]])
                if len(unique_scenarios) > 3:
                    preview += f"\n[italic]+ {len(unique_scenarios) - 3} more[/italic]"
                table.add_row(issue_key, preview)
            self.console.print(table)
            self.console.print("\n")

        # 2. GNS3 Table
        if gns3_issues:
            table = Table(
                title="[bold orange3]TIER 3: GNS3 Functional Failures[/bold orange3]",
                show_header=True,
                header_style="bold orange3",
            )
            table.add_column("Scenario & Error Detail", style="white")
            for g_issue in list(set(gns3_issues))[:10]:
                table.add_row(g_issue)
            if len(set(gns3_issues)) > 10:
                table.add_row(
                    f"[italic]+ {len(set(gns3_issues)) - 10} more functional failures[/italic]"
                )
            self.console.print(table)
            self.console.print("\n")

        # 3. Hallucination Table
        found_any_hal = any(items for items in hallucination_issues.values())
        if found_any_hal:
            table = Table(
                title="[bold yellow]AUDIT: Hallucination Patterns Detected[/bold yellow]",
                show_header=True,
                header_style="bold yellow",
            )
            table.add_column("Category", style="yellow")
            table.add_column("Scenario & Detail", style="white")
            for h_type, items in hallucination_issues.items():
                if items:
                    for item in list(set(items))[:3]:
                        table.add_row(h_type, item)
                    if len(set(items)) > 3:
                        table.add_row(
                            h_type, f"[italic]+ {len(set(items)) - 3} more[/italic]"
                        )
            self.console.print(table)
            self.console.print("\n")
        else:
            self.console.print(
                "[bold green]✅ No hallucinations detected in this run.[/bold green]\n"
            )


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    parser = argparse.ArgumentParser(
        description="RAG-NetTwin Paper Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-vanilla", action="store_true", help="Also run vanilla LLM baseline"
    )
    parser.add_argument("--ablation", action="store_true", help="Run Ablation Study")
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear all caches before running"
    )
    parser.add_argument(
        "--cache-only", action="store_true", help="Use only cached results"
    )
    parser.add_argument(
        "--clear-failed",
        action="store_true",
        help="Clear only failed/error entries from cache",
    )
    parser.add_argument(
        "--re-validate",
        action="store_true",
        help="Re-run validation on cached configs (offline)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively ask to retry failed cached entries",
    )
    parser.add_argument(
        "--run-gns3", action="store_true", help="Run GNS3 functional verification"
    )
    parser.add_argument(
        "--evaluation-mode",
        choices=["strict", "observational"],
        default="strict",
        help="Evaluation mode: 'strict' (short-circuits GNS3 on Batfish failure) or 'observational' (always runs GNS3)",
    )
    args = parser.parse_args()

    if args.clear_cache:
        import glob

        artifacts = [
            f"data/cache/{VANILLA_CACHE_FILE}",
            f"data/cache/{RAG_CACHE_FILE}",
            "data/processed/intent_cache.json",
        ]
        artifacts.extend(glob.glob("results/paper_evaluation_*.json"))
        for file_path in set(artifacts):
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"DELETED: {file_path}")
                except Exception as e:
                    print(f"FAILED TO DELETE {file_path}: {e}")

        print("Clearing Vector Database caches...")
        try:
            # Ensure we can import from src
            import sys

            if os.getcwd() not in sys.path:
                sys.path.append(os.getcwd())

            from src.rag.vector_store import VectorStore

            vs = VectorStore()
            vs.clear_cache()
        except Exception as e:
            print(f"FAILED TO CLEAR VECTOR CACHE: {e}")

        print("--- CACHE PURGE COMPLETE ---")

    if args.clear_failed:
        print("Clearing FAILED/ERROR entries from caches...")
        cm = CacheManager()
        for cache_file in [VANILLA_CACHE_FILE, RAG_CACHE_FILE]:
            filepath = os.path.join(cm.cache_dir, cache_file)
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    try:
                        full_cache = json.load(f)
                        original_count = len(full_cache)
                        cleaned_cache = {
                            k: v
                            for k, v in full_cache.items()
                            if v.get("status") in ["PASS", "WARNING"]
                        }
                        with open(filepath, "w") as fw:
                            json.dump(cleaned_cache, fw, indent=2)
                        print(
                            f"  {cache_file}: Removed {original_count - len(cleaned_cache)} failed entries."
                        )
                    except Exception as e:
                        print(f"  Failed to clear {cache_file}: {e}")

    if args.ablation:
        for mode in ["none", "flat", "tiered", "graph"]:
            print(f"\n--- Running Mode: {mode.upper()} ---")
            evaluator = PaperQualityEvaluator(
                run_vanilla=False,
                cache_only=args.cache_only,
                run_gns3=args.run_gns3,
                re_validate=args.re_validate,
                interactive=args.interactive,
                evaluation_mode=args.evaluation_mode,
            )
            evaluator.run_full_eval(retrieval_mode=mode)
    else:
        evaluator = PaperQualityEvaluator(
            run_vanilla=args.run_vanilla,
            cache_only=args.cache_only,
            run_gns3=args.run_gns3,
            re_validate=args.re_validate,
            interactive=args.interactive,
            evaluation_mode=args.evaluation_mode,
        )
        evaluator.run_full_eval()
