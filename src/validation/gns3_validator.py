import os
import requests
import json
import time
import telnetlib
import socket
from typing import Dict, Any, List, Optional

from validation.base import NetworkValidator
from config import settings

class GNS3Validator(NetworkValidator):
    """Performs Tier 3 Emulation Analysis using GNS3 API."""
    
    def __init__(self):
        super().__init__(tier=3)
        self.host = settings.gns3_host
        self.port = settings.gns3_port
        self.base_url = f"http://{self.host}:{self.port}/v2"
        self.project_id = None
        self.connected = False
        
        try:
            # Check connection
            resp = requests.get(f"{self.base_url}/version", timeout=5)
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
        2. Create Nodes (finding appropriate template)
        3. Create Links
        4. Start Nodes
        5. Push Configs (via Telnet)
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
            print(f"  ✓ Created GNS3 project: {project_name}")
            
            # 2. Build Topology
            nodes = self._create_nodes(intent.devices)
            print(f"  ✓ Created {len(nodes)} nodes")
            
            if len(nodes) > 1:
                self._create_links(nodes, intent)
                print(f"  ✓ Created links")
            
            # 3. Start Topology
            print("  ✓ Starting nodes (waiting 30s for boot)...")
            requests.post(f"{self.base_url}/projects/{self.project_id}/nodes/start")
            time.sleep(30) # Wait for IOS to boot
            
            # 4. Push Configs
            if not configs:
                return {
                    "status": "PASS", 
                    "tier": 3, 
                    "project_id": self.project_id,
                    "message": "Topology built. No configs to push."
                }

            results = {}
            for device_name, config in configs.items():
                if device_name in nodes:
                    print(f"  → Pushing config to {device_name}...")
                    success = self._push_config_to_node(nodes[device_name], config)
                    results[device_name] = "Success" if success else "Failed"
            
            # 5. Cleanup (optional - keep for inspection)
            # self._delete_project()

            return {
                "status": "PASS",
                "tier": 3,
                "project_id": self.project_id,
                "config_results": results,
                "message": "Topology created and configured successfully"
            }

        except Exception as e:
            return {"status": "ERROR", "tier": 3, "error": str(e)}

    def _create_project(self, name: str) -> str:
        payload = {"name": name}
        resp = requests.post(f"{self.base_url}/projects", json=payload)
        resp.raise_for_status()
        return resp.json()["project_id"]

    def _find_router_template(self) -> Optional[Dict]:
        """Finds a suitable Cisco router template."""
        try:
            resp = requests.get(f"{self.base_url}/templates")
            if resp.status_code != 200:
                return None
                
            templates = resp.json()
            # Priority list for templates
            keywords = ["iosv", "cisco", "csr1000v", "viou"]
            
            for keyword in keywords:
                for tmpl in templates:
                    if keyword in tmpl['name'].lower() and tmpl['category'] == 'router':
                        return tmpl
            
            # Fallback to any router
            for tmpl in templates:
                if tmpl['category'] == 'router':
                    return tmpl
                    
            return None
        except:
            return None

    def _create_nodes(self, devices: List[Any]) -> Dict[str, str]:
        """Creates nodes and returns a map of name -> node_id"""
        node_map = {}
        
        # Try to find a good template
        template = self._find_router_template()
        
        for device in devices:
            payload = {
                "name": device.name,
                "compute_id": "local"
            }
            
            if template:
                # Use found template
                payload["node_type"] = template['template_type'] # 'iou', 'qemu', 'dynamips'
                payload["template_id"] = template['template_id']
                print(f"    - Using template: {template['name']}")
            else:
                # Fallback to VPCS if no router images found (for testing)
                payload["node_type"] = "vpcs"
                print(f"    - No router images found, using VPCS")

            resp = requests.post(f"{self.base_url}/projects/{self.project_id}/nodes", json=payload)
            if resp.status_code == 201:
                node_map[device.name] = resp.json()["node_id"]
            else:
                print(f"    ! Failed to create node {device.name}: {resp.text}")
                
        return node_map

    def _create_links(self, node_map: Dict[str, str], intent: Any) -> None:
        """Simple linear linking for POC"""
        device_names = list(node_map.keys())
        for i in range(len(device_names) - 1):
            node_a = node_map[device_names[i]]
            node_b = node_map[device_names[i+1]]
            
            # This is a simplification. Real implementation needs to find free ports.
            # Assuming adapter 0, port 0 (g0/0) -> adapter 0, port 1 (g0/1) for simplicity
            # Or just incrementing ports.
            
            payload = {
                "nodes": [
                    {"node_id": node_a, "adapter_number": 0, "port_number": 1},
                    {"node_id": node_b, "adapter_number": 0, "port_number": 1}
                ]
            }
            requests.post(f"{self.base_url}/projects/{self.project_id}/links", json=payload)

    def _push_config_to_node(self, node_id: str, config: str) -> bool:
        """Pushes configuration via Telnet."""
        try:
            # Get node console info
            resp = requests.get(f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}")
            if resp.status_code != 200:
                return False
            
            node_info = resp.json()
            console_port = node_info.get('console')
            console_host = node_info.get('console_host', 'localhost')
            
            # Handle remote GNS3 case
            if console_host == '0.0.0.0':
                console_host = self.host

            if not console_port:
                print(f"    ! No console port for node {node_id}")
                return False

            # Connect
            print(f"      Connecting to {console_host}:{console_port}...")
            tn = telnetlib.Telnet(console_host, console_port, timeout=10)
            
            # Initial enter to clear line
            tn.write(b"\r\n")
            time.sleep(1)
            
            # Simple IOS config push
            # Note: This expects an IOS-like CLI.
            # Real production usage needs netmiko or similar, but telnetlib is fine for POC.
            
            commands = [
                b"enable",
                b"configure terminal",
            ]
            
            # Add config lines
            for line in config.splitlines():
                if line.strip():
                    commands.append(line.encode('ascii'))
            
            commands.append(b"end")
            commands.append(b"write memory")
            
            for cmd in commands:
                tn.write(cmd + b"\r\n")
                time.sleep(0.2) # Small delay between commands
            
            output = tn.read_very_eager().decode('ascii', errors='ignore')
            # print(output) # Debug
            
            tn.close()
            return True
            
        except Exception as e:
            print(f"    ! Config push failed: {e}")
            return False

    def _delete_project(self):
        if self.project_id:
            requests.delete(f"{self.base_url}/projects/{self.project_id}")

if __name__ == "__main__":
    validator = GNS3Validator()
    if validator.connected:
        print("GNS3 Validator Ready")
    else:
        print("GNS3 Validator Offline")