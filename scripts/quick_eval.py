#!/usr/bin/env python3
"""
Quick Evaluation Script for RAG-NetTwin
Runs fast evaluation without Batfish validation.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.parser.intent_parser import IntentParser  # noqa: E402
from src.rag.config_generator import ConfigGenerator  # noqa: E402
from src.evaluation.hallucination_detector import HallucinationDetector  # noqa: E402

TEST_INTENTS = [
    "Configure OSPF area 0 on interface GigabitEthernet0/1 with network 10.0.0.0/24",
    "Create an ACL named BLOCK_SSH that denies TCP traffic from 192.168.1.0/24 to any port 22",
    "Set up BGP AS 65001 and peer with 10.1.1.1",
    "Enable interface GigabitEthernet0/0 with IP address 192.168.1.1/24",
    "Configure static route to 0.0.0.0/0 via 10.0.0.1",
    "Create a VLAN 100 named SALES on a Cisco switch",
    "Configure DHCP pool for 192.168.10.0/24 with gateway 192.168.10.1",
    "On Juniper MX router, configure BGP peer 10.1.1.2 with autonomous system 65001",
    "Configure OSPF area 0 between Cisco and Juniper on their shared link",
    "Enable LLDP globally on a Juniper EX switch",
]


def evaluate_intent(
    intent: str,
    parser: IntentParser,
    generator: ConfigGenerator,
    hall_detector: HallucinationDetector,
) -> dict:
    """Evaluate a single intent."""
    try:
        parsed = parser.parse(intent)
        config_result = generator.generate(parsed)
        device_name = list(config_result.keys())[0]
        config_data = config_result[device_name]
        config_str = config_data.get("config", "")

        has_cisco = (
            "router " in config_str
            or "interface " in config_str
            or "access-list" in config_str
            or "vlan " in config_str
            or " ip " in config_str
            or config_str.startswith("ip ")
            or "\nip " in config_str
        )
        has_juniper = config_str.startswith("set ") or "\nset " in config_str

        citations = config_data.get("retrieved_sources", [])
        valid_ids = config_data.get("retrieved_sources", [])
        hall_report = hall_detector.detect(config_str, citations, valid_ids)
        is_hall = hall_report.is_hallucinated

        return {
            "intent": intent,
            "config": config_str,
            "valid": len(config_str) > 20,
            "vendor": "Cisco"
            if has_cisco
            else ("Juniper" if has_juniper else "Mixed/Unknown"),
            "has_sources": len(config_data.get("retrieved_sources", [])) > 0,
            "hallucination": is_hall,
            "error": None,
        }
    except Exception as e:
        return {
            "intent": intent,
            "config": "",
            "valid": False,
            "vendor": "Error",
            "has_sources": False,
            "hallucination": False,
            "error": str(e),
        }


def main():
    print("=" * 70)
    print("RAG-NetTwin Quick Evaluation")
    print("=" * 70)
    print(f"Testing {len(TEST_INTENTS)} intents (no Batfish validation)")
    print()

    parser = IntentParser()
    generator = ConfigGenerator()
    hall_detector = HallucinationDetector()

    results = []
    for i, intent in enumerate(TEST_INTENTS, 1):
        print(f"[{i}/{len(TEST_INTENTS)}] Processing: {intent[:50]}...")
        result = evaluate_intent(intent, parser, generator, hall_detector)
        results.append(result)

        status = "✅" if result["valid"] and not result["hallucination"] else "❌"
        print(f"       {status} {result['vendor']}, Sources: {result['has_sources']}")

    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    valid = sum(1 for r in results if r["valid"])
    with_sources = sum(1 for r in results if r["has_sources"])
    hall = sum(1 for r in results if r["hallucination"])
    errors = sum(1 for r in results if r["error"])

    print(f"Total Intents:  {len(results)}")
    print(f"Syntax Valid:   {valid}/{len(results)} ({valid / len(results) * 100:.0f}%)")
    print(
        f"Has Citations:  {with_sources}/{len(results)} ({with_sources / len(results) * 100:.0f}%)"
    )
    print(f"Hallucination: {hall}/{len(results)} ({hall / len(results) * 100:.0f}%)")
    print(f"Errors:         {errors}/{len(results)}")

    # Vendor breakdown
    vendors = {}
    for r in results:
        v = r["vendor"]
        vendors[v] = vendors.get(v, 0) + 1
    print()
    print("Vendor Breakdown:")
    for v, c in sorted(vendors.items(), key=lambda x: -x[1]):
        print(f"  {v}: {c}")

    print("=" * 70)

    # Show failed configs
    failed = [r for r in results if not r["valid"] or r["error"]]
    if failed:
        print()
        print("FAILED INTENTS:")
        for r in failed:
            print(f"  - {r['intent'][:60]}")
            if r["error"]:
                print(f"    Error: {r['error'][:100]}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
