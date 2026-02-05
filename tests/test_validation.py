import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validation.batfish_validator import BatfishValidator

def test_batfish_validation():
    """Test the BatfishValidator with a known-bad configuration."""
    validator = BatfishValidator()
    
    if not validator.session:
        print("Skipping Batfish test (service not available).")
        return

    # Configuration with a shadowed ACL rule
    bad_configs = {
        "Router-X": """
interface GigabitEthernet0/0
 ip address 10.0.0.1 255.255.255.0
!
ip access-list extended SHADOW_TEST
 permit ip any any
 deny ip 172.16.0.0 0.0.255.255 any
!
"""
    }
    
    print("Testing Batfish Validation\n")
    print("=" * 60)
    
    result = validator.validate(bad_configs)
    print(json.dumps(result, indent=2))
    
    if result['status'] in ["FAIL", "WARNING"]:
        print("\n[✓] Success: Validator correctly identified issues.")
    else:
        print("\n[!] Unexpected: Validator did not find the shadowed rule.")

if __name__ == "__main__":
    test_batfish_validation()