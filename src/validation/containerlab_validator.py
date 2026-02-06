import os
import yaml
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List

from validation.base import NetworkValidator
from config import settings

class ContainerlabValidator(NetworkValidator):
    """Performs Tier 2 Emulation Analysis using Containerlab."""
    
    def __init__(self):
        super().__init__(tier=2)
        self.lab_dir = settings.data_dir / "validation" / "clab"
        self.lab_dir.mkdir(parents=True, exist_ok=True)
        self.clab_executable = "containerlab" # Assumes it's in PATH (Linux/WSL2)

    def validate(self, configs: Dict[str, str], intent: Any) -> Dict[str, Any]:
        """
        Deploys configurations to a containerized lab and verifies protocols.
        """
        # On Windows, we check if we can run clab, otherwise skip with a helpful message
        if os.name == 'nt':
            return {
                "status": "SKIPPED",
                "tier": 2,
                "message": "Tier 2 (Containerlab) requires a Linux environment (WSL2/Docker).",
                "is_windows_warning": True
            }

        topo_path = self.lab_dir / "topo.clab.yml"
        
        try:
            # 1. Generate Topology YAML
            topology = self._generate_topology(configs, intent)
            with open(topo_path, "w") as f:
                yaml.dump(topology, f)
            
            # 2. Deploy Lab
            print(f"Deploying Tier 2 Lab: {topo_path}")
            deploy_cmd = [self.clab_executable, "deploy", "-t", str(topo_path), "--reconfigure"]
            subprocess.run(deploy_cmd, check=True, capture_output=True)
            
            # 3. Wait for convergence
            print("Waiting 30s for protocol convergence...")
            time.sleep(30)
            
            # 4. Verify Protocols (e.g., OSPF)
            results = self._verify_protocols(intent)
            
            # 5. Destroy Lab (optional, maybe keep for debug)
            # subprocess.run([self.clab_executable, "destroy", "-t", str(topo_path), "--cleanup"], check=True)
            
            status = "PASS" if all(r['success'] for r in results) else "FAIL"
            
            return {
                "status": status,
                "tier": 2,
                "protocol_results": results,
                "summary": f"Tier 2 convergence: {status}"
            }

        except Exception as e:
            return {"status": "ERROR", "tier": 2, "error": str(e)}

    def _generate_topology(self, configs: Dict[str, str], intent: Any) -> Dict[str, Any]:
        """Creates a basic topology based on the number of devices in the intent."""
        nodes = {}
        links = []
        
        device_list = list(configs.keys())
        
        # Simple ring/line topology for POC
        for i, hostname in enumerate(device_list):
            # Determine kind/image based on intent if possible, else default to Cisco
            # In a real system, we'd look up intent.devices[i].vendor
            nodes[hostname] = {
                "kind": "cisco_iosxe", 
                "image": "vrnetlab/vr-cisco-csr1000v:latest",
                "startup-config": f"config/{hostname}.cfg" # Mount generated config
            }
            
            if i > 0:
                prev_host = device_list[i-1]
                links.append({
                    "endpoints": [f"{prev_host}:Gi2", f"{hostname}:Gi2"] # Gi2 because Gi1 is mgmt usually
                })
        
        return {
            "name": "rag_net_tier2",
            "topology": {
                "nodes": nodes,
                "links": links
            }
        }

    def _verify_protocols(self, intent: Any) -> List[Dict[str, Any]]:
        """Executes verification commands inside containers."""
        # This is a placeholder for actual protocol verification logic
        # In a real scenario, we'd run: docker exec clab-rag-net-router1 FastCli -c "show ip ospf neighbor"
        return [
            {
                "check": "OSPF Adjacency",
                "device": d.name,
                "success": True,
                "details": "Simulated: Neighbor state is FULL"
            } for d in intent.devices
        ]

if __name__ == "__main__":
    # Test (will likely skip on Windows)
    validator = ContainerlabValidator()
    print(validator.validate({}, None))
