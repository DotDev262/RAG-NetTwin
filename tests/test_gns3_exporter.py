import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.intent_parser import StructuredIntent, DeviceIntent
from exporter.gns3_exporter import GNS3Exporter

def test_export():
    # 1. Create a manual StructuredIntent
    intent = StructuredIntent(
        original_text="Configure OSPF between R1 and R2",
        protocol="OSPF",
        action="configure",
        devices=[
            DeviceIntent(name="R1", vendor="cisco", os_type="ios-xe"),
            DeviceIntent(name="R2", vendor="juniper", os_type="junos")
        ],
        parameters={"area": "0"}
    )

    # 2. Initialize Exporter
    exporter = GNS3Exporter()

    # 3. Export to a test file
    output_path = "results/test_topology.gns3"
    exporter.export(intent, output_path=output_path)

    # 4. Verify file existence
    if os.path.exists(output_path):
        print(f"✅ Success: Topology exported to {output_path}")
        # Basic content check
        import json
        with open(output_path, "r") as f:
            data = json.load(f)
            assert data["name"].startswith("Twin_")
            assert len(data["topology"]["nodes"]) == 2
            assert len(data["topology"]["links"]) == 1
            print("✅ Success: Topology JSON structure validated.")
    else:
        print(f"❌ Failure: Topology file not found at {output_path}")

if __name__ == "__main__":
    test_export()
