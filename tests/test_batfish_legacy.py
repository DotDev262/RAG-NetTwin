
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.batfish_validator import BatfishValidator

def test_legacy_batfish_validation():
    print("="*60)
    print("TESTING BATFISH VALIDATION FOR LEGACY CISCO (IOS 15.6)")
    print("="*60)

    # 1. The configuration we generated earlier
    legacy_config = """! Based on [chunk_001690]
enable
configure terminal
router ospf 10
 network 0.0.0.0 255.255.255.255 area 0
interface GigabitEthernet0/0
 ip ospf 10 area 0
exit
end
"""
    configs = {"Router-Legacy": legacy_config}

    # 2. Initialize Batfish Validator
    print("
[1] Initializing Batfish Validator...")
    validator = BatfishValidator()
    
    if not validator.session:
        print("
[SKIP] Batfish service not available. Make sure the Docker container is running.")
        return

    # 3. Run Validation
    print("
[2] Running Static Analysis...")
    result = validator.validate(configs)

    # 4. Display Results
    print("
--- Validation Results ---")
    print(f"Status: {result['status']}")
    
    if result['status'] != "SKIPPED":
        print(f"Summary: {result.get('summary', 'No summary available')}")
        
        if result.get('issues'):
            print("
Issues Found:")
            for issue in result['issues']:
                print(f" - [{issue['severity']}] {issue['type']}: {issue['details']}")
        else:
            print("
✓ No static issues detected!")

    print("
" + "="*60)

if __name__ == "__main__":
    try:
        test_legacy_batfish_validation()
    except Exception as e:
        print(f"Error during test: {e}")
