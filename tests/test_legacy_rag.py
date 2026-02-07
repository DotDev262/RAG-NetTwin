import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Also add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser.intent_parser import IntentParser
from src.rag.config_generator import ConfigGenerator

def test_legacy_cisco_generation():
    print("="*60)
    print("TESTING RAG GENERATION FOR LEGACY CISCO (IOS 15.6)")
    print("="*60)

    # 1. Define a legacy intent
    parser = IntentParser()
    intent_text = "Configure OSPF process 10 on Router-Legacy (Cisco 15.6) for interface GigabitEthernet0/0 in area 0"
    
    print(f"\n[1] Parsing Intent: {intent_text}")
    structured_intent = parser.parse(intent_text)
    
    device = structured_intent.devices[0]
    print(f"    Detected: {device.vendor} {device.os_type} {device.os_version}")

    # 2. Generate Configuration
    print("\n[2] Generating Configuration via RAG...")
    generator = ConfigGenerator()
    results = generator.generate(structured_intent)

    # 3. Display Results
    for device_name, data in results.items():
        print(f"\n--- Generated Config for {device_name} ---")
        print(data['config'])
        print("\nRetrieved Sources:")
        # Show unique sources
        unique_sources = list(set(data['retrieved_sources']))
        for source in sorted(unique_sources):
            print(f" - {source}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    try:
        test_legacy_cisco_generation()
    except Exception as e:
        import traceback
        print(f"Error during test: {e}")
        traceback.print_exc()