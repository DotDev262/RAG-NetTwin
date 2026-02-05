import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.intent_parser import IntentParser

def test_intent_parsing():
    """Test IntentParser with various scenarios"""
    try:
        parser = IntentParser()
    except ValueError as e:
        print(f"Skipping test: {e}")
        return

    test_scenarios = [
        "Configure OSPF area 0 on Router-1 (Cisco 17.6)",
        "Block all traffic from 10.0.0.0/8 on the core switch",
        "Set up a static route to 192.168.10.0/24 via 10.1.1.1 on Router-B",
        "Enable VLAN 10 named 'Production' on all access switches",
        "Show the OSPF neighbor status for Router-Alpha"
    ]
    
    print("Testing Intent Parser\n")
    print("=" * 60)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\nScenario {i}: '{scenario}'")
        print("-" * 60)
        
        try:
            result = parser.parse(scenario)
            print(result.model_dump_json(indent=2))
        except Exception as e:
            print(f"Failed to parse scenario {i}: {e}")

if __name__ == "__main__":
    test_intent_parsing()