import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.intent_parser import IntentParser
from rag.config_generator import ConfigGenerator

def test_pipeline():
    load_dotenv()
    
    print("="*60)
    print(" END-TO-END PIPELINE TEST ")
    print("="*60)
    
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment.")
        return

    try:
        # 1. Initialize
        print("\n[1/4] Initializing Components...")
        parser = IntentParser()
        generator = ConfigGenerator()
        print("      ✓ Components ready.")

        # 2. Parse Intent
        intent_text = "Configure OSPF process 1 on Router-1 (Cisco 17.6) for interface Gig0/1 with IP 192.168.1.1/24 in area 0"
        print(f"\n[2/4] Parsing Intent: '{intent_text}'")
        intent = parser.parse(intent_text)
        print("      ✓ Parsed Intent JSON:")
        print(intent.model_dump_json(indent=8))

        # 3. Generate Config
        print("\n[3/4] Generating Configuration via RAG...")
        configs = generator.generate(intent)
        
        # 4. Display Results
        print("\n[4/4] Final Results:")
        print("-" * 40)
        for device, data in configs.items():
            print(f"Device: {device}")
            print(f"Sources: {data['retrieved_sources']}")
            print("\nGenerated CLI:")
            print(data['config'])
            print("-" * 40)

    except Exception as e:
        print(f"\n[!] Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline()