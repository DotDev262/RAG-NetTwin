#!/usr/bin/env python3
"""
Accurate Quick Evaluation Script for RAG-NetTwin.
Uses the PaperQualityEvaluator logic to get "proper results" (Tier 1-3 metrics).
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is in sys.path for imports
root_path = Path(__file__).parent.parent
sys.path.append(str(root_path))

from run_paper_eval import PaperQualityEvaluator  # noqa: E402
from src.utils import setup_logger  # noqa: E402

logger = setup_logger("PaperQuickEval")

QUICK_TEST_INTENTS = [
    "Configure OSPF area 0 on Gig1/0/1 with IP 10.10.10.1/24",
    "Set up BGP with neighbor 192.168.50.1 remote-as 65000 on Cisco",
    "Configure a firewall filter on Juniper to discard ICMP from 10.0.0.0/8",
    "Create an ACL named BLOCK_WEB to deny TCP port 80 from any source",
]


def main():
    parser = argparse.ArgumentParser(description="RAG-NetTwin Accurate Quick Eval")
    parser.add_argument("intent", nargs="?", help="Optional single intent to test")
    parser.add_argument("--run-gns3", action="store_true", help="Run GNS3 validation")
    parser.add_argument(
        "--retrieval-mode",
        default="tiered",
        choices=["tiered", "flat", "graph", "none"],
    )
    args = parser.parse_args()

    evaluator = PaperQualityEvaluator(
        run_vanilla=False,
        cache_only=False,
        run_gns3=args.run_gns3,
        re_validate=False,
        interactive=False,
    )

    if args.intent:
        logger.info(f"Evaluating single intent: {args.intent}")
        parsed_intents = evaluator.parser.parse_batch([args.intent])
        results = [
            evaluator.evaluate_intent(
                parsed_intents[0], retrieval_mode=args.retrieval_mode
            )
        ]
    else:
        logger.info(f"Running {len(QUICK_TEST_INTENTS)} quick test cases...")
        parsed_intents = evaluator.parser.parse_batch(QUICK_TEST_INTENTS)
        results = []
        for intent in parsed_intents:
            results.append(
                evaluator.evaluate_intent(intent, retrieval_mode=args.retrieval_mode)
            )

    # Use the same stats reporter as the paper eval
    evaluator.stats_reporter.generate_summary_table(results, args.retrieval_mode)

    # Print individual results for clarity
    for i, res in enumerate(results):
        print(f"\n{'='*80}")
        print(f" RESULT #{i+1}: {res['scenario']}")
        print(f"{'='*80}")

        rag = res.get("rag_nettwin", {})
        status = rag.get("status", "UNKNOWN")
        print(f"Overall Status: {status}")

        # 1. Batfish (Tier 1) Detailed Report
        print("\n[TIER 1] Batfish Static Analysis:")
        if rag.get("issues"):
            for issue in rag["issues"]:
                color = "🔴" if issue["severity"] == "HIGH" else "🟡"
                print(f"  {color} {issue['type']}: {issue['details']}")
        else:
            print("  ✅ No static analysis issues found.")

        # 2. Hallucination (Audit Trail) Detailed Report
        print("\n[AUDIT] Hallucination Detector:")
        hals = rag.get("hallucinations", [])
        if not hals:
            print("  ✅ No hallucinations detected.")
        else:
            for j, hal in enumerate(hals):
                if hal.get("is_hallucinated"):
                    print(f"  ⚠️ Device {j+1} Issues: {hal.get('reason')}")
                else:
                    print(f"  ✅ Device {j+1}: Clean.")

        # 3. Config & Citations
        configs = rag.get("configs", {})
        retrieved_sources = rag.get("retrieved_sources", [])

        print("\n[OUTPUT] Generated Configurations:")
        for idx, (dev, cfg) in enumerate(configs.items()):
            print(f"\n--- {dev} ---")
            print(cfg)

            # Match sources to device index if possible
            if idx < len(retrieved_sources):
                sources = retrieved_sources[idx]
                if sources:
                    print(f"🔗 Citations: {', '.join(sources)}")
                else:
                    print("🔗 No documentation sources cited.")


if __name__ == "__main__":
    main()
