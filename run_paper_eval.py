import json
import time
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from llm import LLMProvider
from config import settings


class PaperQualityEvaluator:
    """
    Automated high-scale evaluation script to generate data for the PAPER.md.
    Uses batching and rate-limiting to respect API quotas.
    """

    def __init__(self):
        self.parser = IntentParser()
        self.generator = ConfigGenerator()
        self.validator = BatfishValidator()
        self.vanilla_llm = LLMProvider.get_llm(temperature=0.1)

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
        ]

    def run_full_eval(self):
        scenarios = self.get_test_intents()
        all_results = []

        # 0. Metadata for tracking
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        metadata = {
            "timestamp": timestamp,
            "llm_provider": settings.llm_provider,
            "gemini_model": settings.gemini_model,
            "groq_model": settings.groq_model,
            "prompt_version": "v2.0-batch-synthesis",  # Incremented for batch changes
        }

        print(f"🚀 Phase 1: Parsing {len(scenarios)} intents...")
        parsed_intents = []
        for scenario in scenarios:
            try:
                print(f"  Parsing: {scenario[:40]}...")
                parsed_intents.append(self.parser.parse(scenario))
                time.sleep(2)  # Rate limit between parsing calls
            except Exception as e:
                print(f"      ⚠️  Parsing failed: {e}")
                time.sleep(5)  # Extra delay on failure

        print(f"🚀 Phase 2: Generating and Validating configurations...")
        for intent in tqdm(parsed_intents):
            res = self.evaluate_intent(intent)
            if res:
                all_results.append(res)
            time.sleep(5)  # Rate limit cooling between intents

        # 3. Save results with versioning
        os.makedirs("results/history", exist_ok=True)
        report = {"metadata": metadata, "results": all_results}

        # Save to latest for easy access
        with open("results/paper_evaluation_latest.json", "w") as f:
            json.dump(report, f, indent=2)

        # Save to history for tracking
        history_path = f"results/history/eval_{timestamp}.json"
        with open(history_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Evaluation saved to {history_path}")
        self._generate_summary_table(all_results)

    def evaluate_intent(self, intent):
        results = {
            "scenario": intent.original_text,
            "parsed_intent": intent.model_dump(),
        }

        # 1. Vanilla
        try:
            vanilla_cfg = self._generate_vanilla(intent.original_text)
            # Vanilla usually puts all configs in one block, let's treat it as one device
            validation = self.validator.validate({"Vanilla-Router": vanilla_cfg})
            results["vanilla"] = {
                "config": vanilla_cfg,
                "validation": validation,
                "cfr": self._check_cfr(intent, vanilla_cfg, validation),
                "citation_validity": 0.0,  # Vanilla doesn't cite
            }
        except Exception as e:
            results["vanilla"] = {"status": "ERROR", "error": str(e)}

        # 2. RAG with Self-Correction (Retry Loop)
        try:
            rag_output = self.generator.generate(intent)

            # Prepare all configs for multi-device validation
            full_config_map = {
                dev_name: dev_data["config"]
                for dev_name, dev_data in rag_output.items()
            }
            validation = self.validator.validate(full_config_map)

            # --- SELF-CORRECTION LOOP (1 attempt) ---
            if validation["status"] in ["FAIL", "REJECT_FOR_MANUAL_REVIEW"]:
                scenario_desc = (
                    intent.original_text[:30]
                    if intent.original_text
                    else "Unknown Intent"
                )
                print(f"      🔄  Attempting self-correction for {scenario_desc}...")
                refined_map = {}
                for dev_name, config in full_config_map.items():
                    # Identify errors for this specific device
                    dev_errors = [
                        i["details"]
                        for i in validation.get("issues", [])
                        if dev_name in str(i.get("details", ""))
                    ]
                    if not dev_errors:
                        refined_map[dev_name] = config
                        continue

                    # Find vendor from intent
                    vendor = "cisco"
                    for d in intent.devices:
                        if d.name == dev_name:
                            vendor = d.vendor
                            break

                    refined_map[dev_name] = self.generator.refine(
                        dev_name, config, "\n".join(dev_errors[:3]), vendor
                    )

                # Re-validate refined configs
                validation = self.validator.validate(refined_map)
                full_config_map = refined_map
            # ----------------------------------------

            full_config_text = "\n".join(full_config_map.values())

            # Check citation validity across all devices
            valid_citations = [
                1.0 if "! Based on [Ref:" in cfg else 0.0
                for cfg in full_config_map.values()
            ]
            avg_citation_validity = (
                sum(valid_citations) / len(valid_citations) if valid_citations else 0.0
            )

            results["rag_locked"] = {
                "configs": full_config_map,
                "validation": validation,
                "cfr": self._check_cfr(intent, full_config_text, validation),
                "citation_validity": avg_citation_validity,
            }
        except Exception as e:
            import traceback

            print(f"      ⚠️  RAG evaluation failed: {e}\n{traceback.format_exc()}")
            results["rag_locked"] = {"status": "ERROR", "error": str(e)}

        return results

    def _check_cfr(self, intent, config, validation) -> bool:
        """
        Estimates Critical Failure Rate (CFR).
        Returns True if the config passes syntactic checks (PASS/WARNING)
        but is missing critical parameters from the intent (Silent Failure).
        """
        if validation["status"] not in ["PASS", "WARNING"]:
            return False  # Not a "silent" failure

        # Heuristic: Check if critical parameters (IP, AS, Area) are present in the config
        critical_params = []
        if intent.parameters:
            for val in intent.parameters.values():
                if isinstance(val, str) and ("." in val or val.isdigit()):
                    critical_params.append(val)

        for param in critical_params:
            if param not in config:
                return True  # Missing a critical parameter!

        return False

    def _generate_vanilla(self, scenario: str) -> str:
        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_template(
            "Task: Generate Cisco/Juniper CLI for {request}. Output ONLY the raw commands. NO prose. CLI:"
        )
        chain = prompt | self.vanilla_llm
        return chain.invoke({"request": scenario}).content

    def _generate_summary_table(self, results: List[Dict]):
        summary = []
        for mode in ["vanilla", "rag_locked"]:
            mode_data = [
                r[mode] for r in results if mode in r and "status" not in r[mode]
            ]
            if not mode_data:
                continue

            valid_count = sum(
                1 for d in mode_data if d["validation"]["status"] == "PASS"
            )
            cfr_count = sum(1 for d in mode_data if d.get("cfr", False))
            citation_val = sum(
                d.get("citation_validity", 0.0) for d in mode_data
            ) / len(mode_data)

            summary.append(
                {
                    "Mode": mode,
                    "Syntactic Validity": f"{(valid_count / len(mode_data)) * 100:.1f}%",
                    "Hallucination Rate": f"{(1 - valid_count / len(mode_data)) * 100:.1f}%",
                    "CFR": f"{(cfr_count / len(mode_data)) * 100:.1f}%",
                    "Citation Validity": f"{citation_val * 100:.1f}%",
                }
            )
        print("\n📊 FINAL PAPER METRICS")
        print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    evaluator = PaperQualityEvaluator()
    evaluator.run_full_eval()
