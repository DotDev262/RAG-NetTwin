import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator

def test_multi_vendor_pipeline():
    load_dotenv()
    
    print("="*60)
    print(" MULTI-VENDOR PIPELINE TEST (Cisco & Juniper) ")
    print("="*60)
    
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment.")
        return

    try:
        # 1. Initialize
        print("\n[1/3] Initializing Components...")
        parser = IntentParser()
        generator = ConfigGenerator()
        print("      ✓ Components ready.")

        # 2. Multi-Vendor Intent
        intent_text = (
            "Configure OSPF area 0 between Router-Cisco (IOS-XE 17.6) and "
            "Router-Juniper (JunOS 21.4). Use network 10.255.0.0/30 for the point-to-point link."
        )
        print(f"\n[2/3] Parsing Multi-Vendor Intent: \n'{intent_text}'")
        intent = parser.parse(intent_text)
        print("\n      ✓ Parsed Intent JSON:")
        print(intent.model_dump_json(indent=8))

        # 3. Generate Multi-Vendor Config
        print("\n[3/3] Generating Multi-Vendor Configurations via RAG...")
        configs = generator.generate(intent)
        
        # 4. Display Results
        print("\nFinal Results:")
        print("=" * 60)
        for device_name, data in configs.items():
            device_info = next(d for d in intent.devices if d.name == device_name)
            print(f"DEVICE: {device_name} ({device_info.vendor.upper()} {device_info.os_type})")
            print(f"SOURCES: {data['retrieved_sources']}")
            print("\nGENERATED CLI:")
            print("-" * 30)
            print(data['config'])
            print("-" * 30)
            print()

    except Exception as e:
        print(f"\n[!] Multi-Vendor Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multi_vendor_pipeline()