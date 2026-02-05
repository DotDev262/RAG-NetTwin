import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validation.gns3_validator import GNS3Validator
from parser.intent_parser import StructuredIntent, DeviceIntent

def test_tier3_gns3():
    """Test the GNS3Validator logic."""
    print("="*60)
    print(" TIER 3 (GNS3) INTEGRATION TEST ")
    print("="*60)
    
    validator = GNS3Validator()
    
    if not validator.connected:
        print("[!] Skipping test: GNS3 server not reachable at http://localhost:3080")
        return

    # Mock intent
    test_intent = StructuredIntent(
        protocol="OSPF",
        action="create",
        devices=[
            DeviceIntent(name="Router-A", vendor="cisco", os_type="ios-xe", os_version="17.6"),
            DeviceIntent(name="Router-B", vendor="cisco", os_type="ios-xe", os_version="17.6")
        ],
        parameters={"area": "0"},
        requirements=["test_adjacency"]
    )
    
    print("\nRunning GNS3 Project Creation...")
    result = validator.validate({}, test_intent)
    
    print("\nResult JSON:")
    print(json.dumps(result, indent=4))
    
    if result["status"] == "PASS":
        print(f"\n[✓] Success: Project created with ID {result.get('project_id')}")
        # Cleanup is handled in validate (commented out) or manual
    else:
        print(f"\n[?] Status: {result['status']}")

if __name__ == "__main__":
    test_tier3_gns3()