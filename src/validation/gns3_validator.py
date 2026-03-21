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
            logger.info("Starting nodes (waiting 30s for boot)...")
            requests.post(f"{self.base_url}/projects/{self.project_id}/nodes/start", json={})
            time.sleep(30) # Wait for IOS to boot
            
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
