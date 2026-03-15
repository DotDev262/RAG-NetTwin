import json
import os
import sys
import time
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator
from validation.batfish_validator import BatfishValidator
from config import settings

def run_mini_test():
    print("🧪 Starting Detailed Mini-Optimization Test...")
    
    # Initialize components
    parser = IntentParser()
    generator = ConfigGenerator()
    validator = BatfishValidator()
    
    # Representative subset of intents
    scenarios = [
        "Configure OSPF area 0 on Gig1/0/1 with IP 10.10.10.1/24 on Cisco",
        "Configure a firewall filter on Juniper to discard ICMP from 10.0.0.0/8",
        "Configure OSPF area 0 between Router-A (Cisco) and Juniper-1 (Juniper) on their shared link"
    ]
    
    results = []
    
    print(f"🚀 Phase 1: Parsing {len(scenarios)} intents...")
    parsed_intents = []
    for s in scenarios:
        print(f"  - Parsing: {s[:50]}...")
        parsed_intents.append(parser.parse(s))
        
    print(f"\n🚀 Phase 2: Generating and Validating (with Reflection)...")
    for intent in parsed_intents:
        print(f"\n{'='*60}")
        print(f"SCENARIO: {intent.original_text}")
        print(f"{'='*60}")
        
        # Initial Generation
        rag_output = generator.generate(intent)
        full_config_map = {dev_name: dev_data["config"] for dev_name, dev_data in rag_output.items()}
        
        print("\n--- GENERATED CONFIG ---")
        for dev, cfg in full_config_map.items():
            print(f"[{dev}]:\n{cfg}\n")
        
        # Validation
        print("Checking Batfish...")
        validation = validator.validate(full_config_map)
        print(f"Status: {validation['status']}")
        
        if validation["status"] in ["FAIL", "REJECT_FOR_MANUAL_REVIEW"]:
            print("\n❌ ISSUES FOUND:")
            for issue in validation.get("issues", []):
                print(f"  - [{issue['type']}] {issue.get('details', '')[:200]}...")
            
            print(f"\n🔄 Attempting Self-Correction...")
            refined_map = {}
            for dev_name, config in full_config_map.items():
                dev_errors = [i["details"] for i in validation.get("issues", []) if f"configs/{dev_name}" in str(i.get("details", ""))]
                if not dev_errors:
                    refined_map[dev_name] = config
                    continue
                
                print(f"  Refining {dev_name}...")
                # Pass vendor from intent
                vendor = "cisco"
                for d in intent.devices:
                    if d.name == dev_name:
                        vendor = d.vendor
                        break
                refined_map[dev_name] = generator.refine(dev_name, config, "\n".join(dev_errors[:2]), vendor)
            
            print("\n--- REFINED CONFIG ---")
            for dev, cfg in refined_map.items():
                print(f"[{dev}]:\n{cfg}\n")
                
            # Final Validation
            validation = validator.validate(refined_map)
            full_config_map = refined_map
            print(f"✨ Final Status: {validation['status']}")
        else:
            print("✅ Clean validation on first try.")

        results.append({
            "scenario": intent.original_text,
            "status": validation["status"],
            "config": full_config_map
        })

    # Summary
    print(f"\n{'='*60}")
    print("📊 MINI TEST SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    warnings = sum(1 for r in results if r["status"] == "WARNING")
    accuracy = (passed + warnings) / len(results)
    
    print(f"Score: {accuracy*100:.1f}% ({passed} Pass, {warnings} Warning, {len(results)-passed-warnings} Fail)")
    
    for r in results:
        indicator = "🟢" if r["status"] in ["PASS", "WARNING"] else "🔴"
        print(f"{indicator} {r['status']}: {r['scenario']}")

if __name__ == "__main__":
    run_mini_test()
