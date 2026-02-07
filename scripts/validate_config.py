#!/usr/bin/env python3
"""
Quick validation script for generated configurations
"""

import sys

sys.path.insert(0, "src")

from validation.batfish_validator import BatfishValidator
from validation.containerlab_validator import ContainerlabValidator
from validation.gns3_validator import GNS3Validator


def validate_config(config_text, tier="all"):
    """
    Validate a configuration using the three-tier system

    Args:
        config_text: The generated configuration
        tier: '1', '2', '3', or 'all'
    """

    print("=" * 60)
    print("THREE-TIER VALIDATION")
    print("=" * 60)

    results = {}

    # Tier 1: Batfish (Static Analysis)
    if tier in ["1", "all"]:
        print("\n🔍 TIER 1: Batfish Static Analysis")
        print("-" * 40)
        try:
            validator = BatfishValidator()
            result = validator.validate(config_text)
            results["tier1"] = result

            if result.get("passed", False):
                print("✅ PASSED - No syntax errors found")
            else:
                print("❌ FAILED")
                if "errors" in result:
                    for error in result["errors"]:
                        print(f"   - {error}")
        except Exception as e:
            print(f"⚠️  Tier 1 not available: {e}")
            print("   Start Batfish: sudo systemctl start batfish")

    # Tier 2: Containerlab (Emulation)
    if tier in ["2", "all"]:
        print("\n🔬 TIER 2: Containerlab Emulation")
        print("-" * 40)
        try:
            validator = ContainerlabValidator()
            # Note: Requires topology file
            print("ℹ️  Tier 2 requires a topology file")
            print("   Create: containerlab deploy -t topology.yml")
        except Exception as e:
            print(f"⚠️  Tier 2 not available: {e}")

    # Tier 3: GNS3 (Simulation)
    if tier in ["3", "all"]:
        print("\n🧪 TIER 3: GNS3 Simulation")
        print("-" * 40)
        try:
            validator = GNS3Validator()
            print("ℹ️  Tier 3 requires GNS3 project setup")
            print("   Check: sudo systemctl status gns3-server")
        except Exception as e:
            print(f"⚠️  Tier 3 not available: {e}")
            print("   Start GNS3: sudo systemctl start gns3-server")

    print("\n" + "=" * 60)
    return results


if __name__ == "__main__":
    # Example usage
    sample_config = """
interface Gig0/1
 ip address 10.1.1.1 255.255.255.0
 no shutdown
!
router ospf 1
 network 10.1.1.0 0.0.0.255 area 0
"""

    print("Validating sample OSPF configuration...\n")
    validate_config(sample_config, tier="all")

    print("\n💡 To validate your own config:")
    print("   uv run python scripts/validate_config.py")
    print("\n💡 To check validator status:")
    print("   sudo ./scripts/install_validators_ubuntu.sh --verify")
