import os
import requests
import json
import time
import telnetlib
import socket
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from validation.base import NetworkValidator
from config import settings
from utils import setup_logger
from parser.intent_parser import StructuredIntent

logger = setup_logger("GNS3Validator")


class PortManager:
    """Manages free ports for GNS3 nodes to avoid conflicts."""
    def __init__(self):
        self.used_ports: Dict[str, List[int]] = {}

    def get_free_port(self, node_id: str) -> int:
        if node_id not in self.used_ports:
            self.used_ports[node_id] = [0] # Reserve adapter 0 for management/future
            return 1
        
        next_port = max(self.used_ports[node_id]) + 1
        self.used_ports[node_id].append(next_port)
        return next_port


class GNS3Validator(NetworkValidator):
    """Performs Tier 3 Emulation Analysis using GNS3 API."""

    def __init__(self):
        super().__init__(tier=3)
        self.host = settings.gns3_host
        self.port = settings.gns3_port
        self.base_url = f"http://{self.host}:{self.port}/v2"
        self.project_id = None
        self.connected = False
        self.port_manager = PortManager()

        try:
            # Check connection
            resp = requests.get(f"{self.base_url}/version", timeout=5)
            if resp.status_code == 200:
                logger.info(f"Connected to GNS3 Server v{resp.json().get('version')}")
                self.connected = True
            else:
                self.connected = False
        except Exception as e:
            logger.warning(f"Could not connect to GNS3: {e}")
            self.connected = False

    def validate(self, configs: Dict[str, str], intent: Optional[StructuredIntent] = None) -> Dict[str, Any]:
        """
        Orchestrates the GNS3 validation workflow.
        """
        if not self.connected:
            return {
                "status": "SKIPPED", 
                "tier": 3,
                "message": "GNS3 server not reachable."
            }

        try:
            # 1. Create/Find Project
            project_name = f"rag_net_validation_{int(time.time())}"
            self.project_id = self._create_project(project_name)
            logger.info(f"Created GNS3 project: {project_name}")
            
            # 2. Build Topology
            devices = intent.devices if intent else []
            nodes = self._create_nodes(devices)
            logger.info(f"Created {len(nodes)} nodes")
            
            if len(nodes) > 1 and intent:
                self._create_links(nodes, intent)
                logger.info(f"Created links")
            
            # 3. Start Topology
            logger.info("Starting nodes...")
            requests.post(f"{self.base_url}/projects/{self.project_id}/nodes/start", json={})
            
            # Intelligent Polling: Wait for nodes to reach a ready state (max 120s)
            boot_success = self._wait_for_nodes_boot(nodes)
            if not boot_success:
                logger.warning("Some nodes may not have booted fully, proceeding with config push anyway.")
            
            # 4. Push Configs
            results = {}
            for device_name, config in configs.items():
                if device_name in nodes:
                    logger.info(f"Pushing config to {device_name}...")
                    success = self._push_config_to_node(nodes[device_name], config)
                    results[device_name] = "Success" if success else "Failed"
            
            status = "PASS" if all(v == "Success" for v in results.values()) else "FAIL"

            return {
                "status": status,
                "tier": 3,
                "project_id": self.project_id,
                "config_results": results,
                "summary": "Tier 3 GNS3 validation complete."
            }

        except Exception as e:
            logger.error(f"Tier 3 validation failed: {e}")
            return {"status": "ERROR", "tier": 3, "error": str(e)}

        except Exception as e:
            logger.error(f"Config push failed: {e}")
            return False

    def verify_functional(
        self, 
        nodes: Dict[str, str], 
        verification_data: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Closed-Loop Verification (Recommendation 1).
        Executes verification commands and returns output.
        """
        logger.info("Starting Functional Intent Verification...")
        # Wait for network convergence
        time.sleep(10)
        
        verification_results = {}
        
        for device_name, commands in verification_data.items():
            if device_name not in nodes or not commands:
                continue
                
            node_id = nodes[device_name]
            logger.info(f"Verifying {device_name}...")
            
            try:
                # Get console info
                resp = requests.get(f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}")
                node_info = resp.json()
                console_port = node_info.get('console')
                console_host = node_info.get('console_host', 'localhost')
                if console_host == '0.0.0.0': console_host = self.host

                with socket.create_connection((console_host, console_port), timeout=5):
                    tn = telnetlib.Telnet(console_host, console_port, timeout=5)
                    
                    outputs = []
                    for cmd in commands:
                        tn.write(cmd.encode("ascii") + b"\r\n")
                        time.sleep(1) # Wait for command output
                        # Read until prompt
                        output = tn.read_very_eager().decode("ascii", errors="ignore")
                        outputs.append({"command": cmd, "output": output})
                    
                    tn.close()
                    verification_results[device_name] = outputs
            except Exception as e:
                logger.error(f"Verification failed for {device_name}: {e}")
                verification_results[device_name] = [{"error": str(e)}]
        
        return verification_results

    def get_network_state(
        self, 
        nodes: Dict[str, str], 
        commands: List[str] = ["show ip route", "show ip interface brief"]
    ) -> Dict[str, Any]:
        """
        Captures a snapshot of the network state for Blast Radius analysis (Recommendation 3).
        """
        logger.info(f"Capturing network state baseline ({len(commands)} commands)...")
        state = {}
        
        for device_name, node_id in nodes.items():
            try:
                resp = requests.get(f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}")
                node_info = resp.json()
                console_port = node_info.get('console')
                console_host = node_info.get('console_host', 'localhost')
                if console_host == '0.0.0.0': console_host = self.host

                with socket.create_connection((console_host, console_port), timeout=5):
                    tn = telnetlib.Telnet(console_host, console_port, timeout=5)
                    
                    device_state = {}
                    for cmd in commands:
                        tn.write(cmd.encode("ascii") + b"\r\n")
                        time.sleep(1)
                        output = tn.read_very_eager().decode("ascii", errors="ignore")
                        device_state[cmd] = output
                    
                    tn.close()
                    state[device_name] = device_state
            except Exception as e:
                logger.error(f"State capture failed for {device_name}: {e}")
        
        return state

    def _wait_for_nodes_boot(self, nodes: Dict[str, str], timeout: int = 120) -> bool:
        """
        Polls the console of all nodes until a prompt is detected.
        Returns True if all nodes are ready, False if timeout reached.
        """
        start_time = time.time()
        pending_nodes = list(nodes.keys())
        
        logger.info(f"Polling console for {len(pending_nodes)} nodes...")
        
        while time.time() - start_time < timeout and pending_nodes:
            for node_name in list(pending_nodes):
                node_id = nodes[node_name]
                try:
                    # Get console info
                    resp = requests.get(f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}")
                    if resp.status_code != 200:
                        continue
                    
                    node_info = resp.json()
                    console_port = node_info.get('console')
                    console_host = node_info.get('console_host', 'localhost')
                    if console_host == '0.0.0.0':
                        console_host = self.host

                    if not console_port:
                        continue

                    # Try a non-blocking Telnet check
                    with socket.create_connection((console_host, console_port), timeout=2):
                        tn = telnetlib.Telnet(console_host, console_port, timeout=2)
                        tn.write(b"\r\n")
                        # Look for common prompts: Router>, Router#, Switch>, user:
                        # We use expect with a short timeout
                        idx, match, text = tn.expect([b">", b"#", b"login:", b"user:"], timeout=2)
                        tn.close()
                        
                        if idx != -1:
                            logger.info(f"Node {node_name} is READY (detected prompt)")
                            pending_nodes.remove(node_name)
                except (ConnectionRefusedError, socket.timeout, EOFError):
                    # Still booting
                    continue
                except Exception as e:
                    logger.debug(f"Polling error for {node_name}: {e}")
                    continue
            
            if pending_nodes:
                time.sleep(2) # Wait between polls
                
        return len(pending_nodes) == 0

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
            keywords = ["iosv", "cisco", "csr1000v", "viou"]
            for keyword in keywords:
                for tmpl in templates:
                    if keyword in tmpl['name'].lower() and tmpl['category'] == 'router':
                        return tmpl
            for tmpl in templates:
                if tmpl['category'] == 'router':
                    return tmpl
            return None
        except Exception:
            return None

    def _create_nodes(self, devices: List[Any]) -> Dict[str, str]:
        """Creates nodes and returns a map of name -> node_id"""
        node_map = {}
        template = self._find_router_template()
        
        for device in devices:
            payload = {
                "name": device.name,
                "compute_id": "local"
            }
            if template:
                payload["node_type"] = template['template_type']
                payload["template_id"] = template['template_id']
                logger.info(f"Using template: {template['name']} for {device.name}")
            else:
                payload["node_type"] = "vpcs"
                logger.warning(f"No router images found, using VPCS for {device.name}")

            resp = requests.post(f"{self.base_url}/projects/{self.project_id}/nodes", json=payload)
            if resp.status_code == 201:
                node_map[device.name] = resp.json()["node_id"]
            else:
                logger.error(f"Failed to create node {device.name}: {resp.text}")
        return node_map

    def _create_links(self, node_map: Dict[str, str], intent: StructuredIntent) -> None:
        """Linear linking using PortManager."""
        device_names = list(node_map.keys())
        for i in range(len(device_names) - 1):
            node_a_id = node_map[device_names[i]]
            node_b_id = node_map[device_names[i+1]]
            
            port_a = self.port_manager.get_free_port(node_a_id)
            port_b = self.port_manager.get_free_port(node_b_id)
            
            payload = {
                "nodes": [
                    {"node_id": node_a_id, "adapter_number": 0, "port_number": port_a},
                    {"node_id": node_b_id, "adapter_number": 0, "port_number": port_b}
                ]
            }
            requests.post(f"{self.base_url}/projects/{self.project_id}/links", json=payload)

    def _push_config_to_node(self, node_id: str, config: str) -> bool:
        """Pushes configuration via Telnet."""
        try:
            resp = requests.get(f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}")
            if resp.status_code != 200:
                return False
            
            node_info = resp.json()
            console_port = node_info.get('console')
            console_host = node_info.get('console_host', 'localhost')
            if console_host == '0.0.0.0':
                console_host = self.host

            if not console_port:
                logger.warning(f"No console port for node {node_id}")
                return False

            logger.info(f"Connecting to {console_host}:{console_port}...")
            tn = telnetlib.Telnet(console_host, console_port, timeout=10)
            tn.write(b"\r\n")
            time.sleep(1)
            
            commands = [b"enable", b"configure terminal"]
            for line in config.splitlines():
                if line.strip():
                    commands.append(line.encode('ascii'))
            commands.append(b"end")
            commands.append(b"write memory")
            
            for cmd in commands:
                tn.write(cmd + b"\r\n")
                time.sleep(0.2)
            
            tn.close()
            return True
        except Exception as e:
            logger.error(f"Config push failed: {e}")
            return False
