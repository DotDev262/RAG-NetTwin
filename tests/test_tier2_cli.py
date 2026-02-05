import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validation.containerlab_validator import ContainerlabValidator
from parser.intent_parser import StructuredIntent, DeviceIntent

def test_tier2_cli():
    """Test the ContainerlabValidator logic via CLI."""
    print("="*60)
    print(" TIER 2 (CONTAINERLAB) CLI TEST ")
    print("="*60)
    
    validator = ContainerlabValidator()
    
    # Mock intent and configs
    test_intent = StructuredIntent(
        protocol="OSPF",
        action="create",
        devices=[DeviceIntent(name="Router-1", vendor="cisco", os_type="ios-xe", os_version="17.6")],
        parameters={"area": "0"},
        requirements=["test_adjacency"]
    )
    
    test_configs = {
        "Router-1": "interface GigabitEthernet0/1\n ip address 10.0.0.1 255.255.255.0\n router ospf 1\n network 10.0.0.0 0.0.0.255 area 0"
    }
    
    print("\nRunning Validation...")
    result = validator.validate(test_configs, test_intent)
    
    print("\nResult JSON:")
    print(json.dumps(result, indent=4))
    
    if result.get("is_windows_warning"):
        print("\n[!] Verified: Validator correctly identified Windows environment and skipped execution.")
    elif result["status"] == "PASS":
        print("\n[✓] Success: Tier 2 validation passed.")
    else:
        print(f"\n[?] Status: {result['status']}")

if __name__ == "__main__":
    test_tier2_cli()