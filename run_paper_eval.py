import json
import time
import os
import argparse
import random
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any
from tqdm import tqdm

# Add src to path for imports

from src.parser.intent_parser import IntentParser
from src.rag.config_generator import ConfigGenerator, CONFIG_GENERATOR_VERSION
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
        parser: Optional[IntentParser] = None,
        generator: Optional[ConfigGenerator] = None,
        validator: Optional[BatfishValidator] = None,
        hallucination_detector: Optional[HallucinationDetector] = None,
        token_counter: Optional[TokenCounter] = None,
    ):
        self.parser = parser or IntentParser()
        self.generator = generator or ConfigGenerator()
        self.validator = validator or BatfishValidator()
        self.hallucination_detector = hallucination_detector or HallucinationDetector()
        self.token_counter = token_counter or TokenCounter()
        self.vanilla_llm = LLMProvider.get_llm(temperature=0.0) if run_vanilla else None
        self.run_vanilla = run_vanilla
        self.cache_only = cache_only
        self.run_gns3 = run_gns3

        self.cache_manager = CacheManager()
        self.cfr_checker = CFRChecker()
        self.stats_reporter = StatsReporter()

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

        logger.info(f"Phase 2: Evaluating... (Retrieval Mode: {retrieval_mode})")
        for intent in tqdm(parsed_intents, desc=f"Evaluating ({retrieval_mode})"):
            res = self.evaluate_intent(intent, retrieval_mode=retrieval_mode)
            if res:
                all_results.append(res)
            time.sleep(2.0)

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

    def evaluate_intent(self, intent, retrieval_mode: str = "tiered"):
        intent_key = self.get_intent_key(intent)
        results = {
            "scenario": intent.original_text,
            "parsed_intent": intent.model_dump(),
        }

        # --- RAG Mode ---
        cache_key = f"{CONFIG_GENERATOR_VERSION}:{retrieval_mode}:{intent_key}"
        cached_rag = self.cache_manager.get(self.rag_cache, cache_key)

        if cached_rag and cached_rag.get("status") not in [
            "PASS",
            "WARNING",
            "REJECT_FOR_MANUAL_REVIEW",
        ]:
            cached_rag = None

        if cached_rag:
            results["rag_nettwin"] = cached_rag
            configs = cached_rag.get("configs", {})
            all_hal_reports = []
            all_sources = []
            for s_list in cached_rag.get("retrieved_sources", []):
                if isinstance(s_list, list):
                    all_sources.extend(s_list)
            all_texts = [t for t in cached_rag.get("retrieved_texts", []) if t]

            for dev_name, config_text in configs.items():
                if dev_name and dev_name.startswith("_"):
                    continue
                hal_report = self.hallucination_detector.detect(
                    config_text,
                    all_sources,
                    [],
                    retrieved_texts=all_texts,
                    intent_context=intent.original_text,
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
                    )
                    all_hal_reports.append(hal_report.model_dump())

                aggregate_config = "\n".join(device_configs.values())
                cfr_failure = self.cfr_checker.check(intent, aggregate_config)

                functional_status = "SKIPPED"
                gns3_car = 0.0
                is_multi_vendor = False

                if self.run_gns3 and self.gns3:
                    try:
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
                            for dev_name, cmd_outputs in v_res.items():
                                outputs_to_check = (
                                    list(cmd_outputs.values())
                                    if isinstance(cmd_outputs, dict)
                                    else cmd_outputs
                                )

                                # Process raw outputs from verify_functional (it returns list of dicts)
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
                                            break
                                if has_functional_error:
                                    break

                            functional_status = (
                                "PASS" if not has_functional_error else "FAIL"
                            )
                        else:
                            functional_status = "FAIL"
                    except Exception as ge:
                        logger.error(f"GNS3 validation failed: {ge}")
                        functional_status = "ERROR"

                # Deep Trace: Aggregate RAG and Functional logs
                deep_trace = rag_output.pop("_trace", {})
                if self.run_gns3 and self.gns3 and "g_res" in locals():
                    deep_trace["telnet_logs"] = g_res.get("telnet_logs", {})

                eval_res = {
                    "scenario": intent.original_text,
                    "configs": device_configs,
                    "status": val_report.get("status"),
                    "functional_status": functional_status,
                    "car": gns3_car,
                    "is_multi_vendor": is_multi_vendor,
                    "latency": latency,
                    "hallucinations": all_hal_reports,
                    "cfr_failure": cfr_failure,
                    "retrieved_sources": [
                        v.get("retrieved_sources", [])
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
                self.cache_manager.set(
                    self.rag_cache, cache_key, eval_res, mode=retrieval_mode
                )
            except Exception as e:
                logger.error(f"RAG Evaluation failed: {e}")
                results["rag_nettwin"] = {"status": "ERROR", "error": str(e)}

        # --- Vanilla LLM ---
        if self.run_vanilla:
            cached_vanilla = self.cache_manager.get(self.vanilla_cache, intent_key)
            if cached_vanilla:
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
                    if self.run_gns3 and self.gns3:
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
                        "functional_status": functional_status,
                        "cfr_failure": self.cfr_checker.check(intent, vanilla_cfg),
                        "hallucination": self.hallucination_detector.detect(
                            vanilla_cfg, [], [], intent_context=intent.original_text
                        ).model_dump(),
                    }
                    results["vanilla"] = vanilla_result
                    self.cache_manager.set(
                        self.vanilla_cache, intent_key, vanilla_result, mode="vanilla"
                    )
                except Exception as e:
                    results["vanilla"] = {"status": "ERROR", "error": str(e)}
        return results

    def _generate_vanilla(self, scenario: str) -> str:
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_template(
            "Task: Generate Cisco/Juniper CLI for {request}. Output ONLY the raw commands. NO prose. CLI:"
        )
        chain = prompt | self.vanilla_llm
        return chain.invoke({"request": scenario}).content

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
        "--run-gns3", action="store_true", help="Run GNS3 functional verification"
    )
    args = parser.parse_args()

    if args.clear_cache:
        import glob

        artifacts = [
            VANILLA_CACHE_FILE,
            RAG_CACHE_FILE,
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
        try:
            from src.rag.vector_store import VectorStore

            vs = VectorStore()
            vs.clear_cache()
        except Exception:
            pass
        print("--- CACHE PURGE COMPLETE ---")

    if args.ablation:
        for mode in ["none", "flat", "tiered"]:
            print(f"\n--- Running Mode: {mode.upper()} ---")
            evaluator = PaperQualityEvaluator(
                run_vanilla=False, cache_only=args.cache_only, run_gns3=args.run_gns3
            )
            evaluator.run_full_eval(retrieval_mode=mode)
    else:
        evaluator = PaperQualityEvaluator(
            run_vanilla=args.run_vanilla,
            cache_only=args.cache_only,
            run_gns3=args.run_gns3,
        )
        evaluator.run_full_eval()
