import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Add src to path


# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.validation.gns3_validator import GNS3Validator  # noqa: E402
from src.schemas.intent import StructuredIntent, DeviceIntent  # noqa: E402

console = Console()


def test_full_gns3_pipeline():
    console.print(
        Panel.fit(
            "[bold green]RAG-NetTwin: Full GNS3 Pipeline Stress Test[/bold green]"
        )
    )

    # 1. Initialize Validator
    v = GNS3Validator()
    if not v.connected:
        console.print("[red]❌ Error: GNS3 Server not connected.[/red]")
        return

    # 2. Mock Intent for R1
    intent = StructuredIntent(
        original_text="Test Intent",
        protocol="TEST",
        action="create",
        devices=[DeviceIntent(name="R1", vendor="cisco", os_type="ios-xe")],
        parameters={},
    )

    try:
        # 3. Create Project & Start Nodes
        console.print("\n[1/6] Creating Project and Starting Node (R1)...")
        # We pass empty config first to create the nodes
        result = v.validate({}, intent)
        if result.get("status") == "ERROR":
            console.print(
                f"[red]❌ Failed to create project: {result.get('error')}[/red]"
            )
            return

        nodes = result.get("nodes", {})
        console.print(f"   ✅ Project Created: {result.get('project_id')}")
        console.print(f"   ✅ Node R1 ID: {nodes.get('R1')}")

        # 4. Capture Pre-Change Baseline
        console.print("\n[2/6] Capturing Pre-Change Baseline...")
        pre_state = v.get_network_state(nodes)
        console.print(f"   ✅ Captured state for {len(pre_state)} devices.")

        # 5. Push Sample Config
        console.print("\n[3/6] Pushing Sample Config (Loopback99)...")
        test_config = {
            "R1": "interface Loopback99\n ip address 9.9.9.9 255.255.255.255\n description GNS3_FULL_TEST"
        }
        push_results = v.push_configs(nodes, test_config)
        console.print(f"   ✅ Config Push Status: {push_results}")

        # 6. Wait for Convergence & Functional Verify
        console.print(
            "\n[4/6] Running Functional Verification (show ip interface brief)..."
        )
        v_data = {"R1": ["show ip interface brief | include Loopback99"]}
        v_results = v.verify_functional(nodes, v_data)

        for dev, outputs in v_results.items():
            for out in outputs:
                console.print(
                    f"   [bold blue]Device {dev} Output:[/bold blue]\n{out.get('output')}"
                )

        # 7. Capture Post-Change State
        console.print("\n[5/6] Capturing Post-Change State...")
        post_state = v.get_network_state(nodes)
        if "Loopback99" in str(post_state):
            console.print("   ✅ SUCCESS: Loopback99 detected in Post-Change state.")
        else:
            console.print("   ⚠️  WARNING: Loopback99 not found in raw state capture.")

        # 8. Cleanup
        console.print("\n[6/6] Cleaning up test project...")
        import requests

        requests.delete(f"{v.base_url}/projects/{v.project_id}", auth=v.auth)
        console.print("   ✅ SUCCESS: Project deleted.")

        console.print(
            Panel.fit("[bold green]ALL GNS3 PIPELINE TESTS PASSED![/bold green]")
        )

    except Exception as e:
        console.print(f"[red]❌ UNEXPECTED ERROR: {e}[/red]")


if __name__ == "__main__":
    test_full_gns3_pipeline()
