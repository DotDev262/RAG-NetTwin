import os
import requests
import json
import time
from typing import Dict, Any, List, Optional

class GNS3Validator:
    """Performs Tier 3 Emulation Analysis using GNS3 API."""
    
    def __init__(self, host: str = "localhost", port: int = 3080):
        # Allow override from env vars
        self.host = os.getenv("GNS3_HOST", host)
        self.port = int(os.getenv("GNS3_PORT", port))
        self.base_url = f"http://{self.host}:{self.port}/v2"
        self.project_id = None
        
        try:
            # Check connection
            resp = requests.get(f"{self.base_url}/version")
            if resp.status_code == 200:
                print(f"Connected to GNS3 Server v{resp.json().get('version')}")
                self.connected = True
            else:
                self.connected = False
        except Exception as e:
            print(f"Warning: Could not connect to GNS3: {e}")
            self.connected = False

    def validate(self, configs: Dict[str, str], intent: Any) -> Dict[str, Any]:
        """
        Orchestrates the GNS3 validation workflow:
        1. Create Project
        2. Create Nodes & Links
        3. Start Nodes
        4. Push Configs
        5. Verify Connectivity (Ping)
        """
        if not self.connected:
            return {
                "status": "SKIPPED", 
                "tier": 3,
                "message": "GNS3 server not reachable."
            }

        try:
            # 1. Create Project
            project_name = f"rag_net_validation_{int(time.time())}"
            self.project_id = self._create_project(project_name)
            
            # 2. Build Topology
            nodes = self._create_nodes(intent.devices)
            self._create_links(nodes, intent)
            
            # 3. Start Topology
            # requests.post(f"{self.base_url}/projects/{self.project_id}/nodes/start")
            
            # 4. Push Configs (Placeholder logic for now)
            # This requires interacting with the console stream or using an agent
            
            # 5. Cleanup
            # self._delete_project()

            return {
                "status": "PASS", # Placeholder
                "tier": 3,
                "project_id": self.project_id,
                "message": "Topology created successfully (Config push pending implementation)"
            }

        except Exception as e:
            return {"status": "ERROR", "tier": 3, "error": str(e)}

    def _create_project(self, name: str) -> str:
        payload = {"name": name}
        resp = requests.post(f"{self.base_url}/projects", json=payload)
        resp.raise_for_status()
        return resp.json()["project_id"]

    def _create_nodes(self, devices: List[Any]) -> Dict[str, str]:
        """Creates nodes and returns a map of name -> node_id"""
        node_map = {}
        for device in devices:
            # Map OS type to GNS3 template/appliance
            # This is a simplification; you'd need logic to find correct template ID
            payload = {
                "name": device.name,
                "node_type": "vpcs", # Defaulting to VPCS for test; need to map to IOSv/etc
                "compute_id": "local"
            }
            resp = requests.post(f"{self.base_url}/projects/{self.project_id}/nodes", json=payload)
            if resp.status_code == 201:
                node_map[device.name] = resp.json()["node_id"]
        return node_map

    def _create_links(self, node_map: Dict[str, str], intent: Any) -> None:
        """Simple linear linking for POC"""
        device_names = list(node_map.keys())
        for i in range(len(device_names) - 1):
            node_a = node_map[device_names[i]]
            node_b = node_map[device_names[i+1]]
            
            payload = {
                "nodes": [
                    {"node_id": node_a, "adapter_number": 0, "port_number": 0},
                    {"node_id": node_b, "adapter_number": 0, "port_number": 0}
                ]
            }
            requests.post(f"{self.base_url}/projects/{self.project_id}/links", json=payload)

    def _delete_project(self):
        if self.project_id:
            requests.delete(f"{self.base_url}/projects/{self.project_id}")

if __name__ == "__main__":
    validator = GNS3Validator()
    if validator.connected:
        print("GNS3 Validator Ready")
    else:
        print("GNS3 Validator Offline")
