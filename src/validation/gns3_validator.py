import warnings

# Suppress telnetlib deprecation warning (slated for removal in Python 3.13)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telnetlib")

import requests  # noqa: E402
import time  # noqa: E402
import telnetlib  # noqa: E402
import socket  # noqa: E402

# noqa: E402
from typing import Dict, Any, List, Optional, cast  # noqa: E402

# noqa: E402
from src.validation.base import NetworkValidator  # noqa: E402
from src.config import settings  # noqa: E402
from src.utils import setup_logger  # noqa: E402
from src.schemas.intent import StructuredIntent  # noqa: E402

logger = setup_logger("GNS3Validator")


class PortManager:
    """Manages free ports for GNS3 nodes to avoid conflicts."""

    def __init__(self) -> None:
        self.used_ports: Dict[str, List[int]] = {}

    def get_free_port(self, node_id: str) -> int:
        if node_id not in self.used_ports:
            self.used_ports[node_id] = [0]  # Reserve adapter 0 for management/future
            return 1

        next_port = max(self.used_ports[node_id]) + 1
        self.used_ports[node_id].append(next_port)
        return next_port


class GNS3Validator(NetworkValidator):
    """Performs Tier 3 Emulation Analysis using GNS3 API."""

    def __init__(self):
        super().__init__(tier=3)
        self.host = (
            settings.gns3_host if settings.gns3_host != "localhost" else "127.0.0.1"
        )
        self.port = settings.gns3_port
        self.base_url = f"http://{self.host}:{self.port}/v2"
        # Updated with credentials from ~/.config/GNS3/2.2/gns3_server.conf
        self.auth = (
            "admin",
            "ZQMSdXR6LVD5rN7gx2ipegzMYPYOZJeo7IJviL87PjgvYK4p8bg1R1fT9YgOTzX9",
        )
        self.project_id = None
        self.connected = False
        self.port_manager = PortManager()

        try:
            # Check connection with auth
            resp = requests.get(f"{self.base_url}/version", timeout=5, auth=self.auth)
            if resp.status_code == 200:
                logger.info(
                    f"Connected to GNS3 Server v{resp.json().get('version')} at {self.host}"
                )
                self.connected = True
            else:
                logger.warning(f"GNS3 Connection failed with status {resp.status_code}")
                self.connected = False
        except Exception as e:
            logger.warning(f"Could not connect to GNS3: {e}")
            self.connected = False

    def validate(
        self, configs: Dict[str, str], intent: Optional[StructuredIntent] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates the GNS3 validation workflow using a persistent project.
        """
        if not self.connected:
            return {
                "status": "SKIPPED",
                "tier": 3,
                "message": "GNS3 server not reachable.",
            }

        try:
            # 1. Reuse or Create Persistent Project
            project_name = "RAG_NetTwin_DigitalTwin"
            self.project_id = self._get_or_create_project(project_name)
            logger.info(
                f"Using persistent GNS3 project: {project_name} ({self.project_id})"
            )

            # 2. Cleanup
            self._cleanup_project()

            # 3. Build Topology
            devices = intent.devices if intent else []
            nodes = self._create_nodes(devices)
            logger.info(f"Created {len(nodes)} nodes")

            if not nodes and devices:
                err_msg = (
                    f"Failed to create any nodes for {len(devices)} requested devices."
                )
                if hasattr(self, "last_errors") and self.last_errors:
                    err_msg += f" Details: {'; '.join(self.last_errors[:3])}"
                return {
                    "status": "FAIL",
                    "tier": 3,
                    "summary": err_msg,
                }

            if len(nodes) > 1 and intent:
                self._create_links(nodes, intent)
                logger.info("Created links")

            # 3. Start Topology
            logger.info("Starting nodes...")
            start_resp = requests.post(
                f"{self.base_url}/projects/{self.project_id}/nodes/start",
                json={},
                auth=self.auth,
            )
            if start_resp.status_code not in [200, 204]:
                err = (
                    f"Failed to start nodes: {start_resp.status_code} {start_resp.text}"
                )
                logger.error(err)
                return {
                    "status": "FAIL",
                    "tier": 3,
                    "summary": err,
                    "project_id": self.project_id,
                }

            # Intelligent Polling: Wait for nodes to reach a ready state (max 300s)
            boot_success = self._wait_for_nodes_boot(nodes)
            if not boot_success:
                logger.warning(
                    "Some nodes may not have booted fully, proceeding with config push anyway."
                )

            # Explicit convergence wait (Recommendation 5)
            logger.info("Nodes ready. Waiting 10s for OS stabilization...")
            time.sleep(10)

            # 4. Push Configs & Track Stats (Recommendation CAR)
            results = {}
            total_commands = 0
            accepted_commands = 0
            telnet_logs = {}
            push_errors = []

            for device_name, config in configs.items():
                if device_name in nodes:
                    # Find vendor for this device
                    vendor = "cisco"
                    if intent and intent.devices:
                        for dev in intent.devices:
                            if dev.name == device_name:
                                vendor = (dev.vendor or "cisco").lower()
                                break

                    logger.info(f"Pushing {vendor} config to {device_name}...")
                    node_stats = self._push_config_to_node(
                        nodes[device_name], config, vendor
                    )
                    telnet_logs[device_name] = node_stats.get("telnet_log", [])

                    if node_stats.get("error"):
                        push_errors.append(f"{device_name}: {node_stats['error']}")

                    if node_stats["total"] > 0:
                        results[device_name] = (
                            "Success"
                            if node_stats["accepted"] == node_stats["total"]
                            else "Partial"
                        )
                        total_commands += node_stats["total"]
                        accepted_commands += node_stats["accepted"]
                    else:
                        results[device_name] = "Failed"

            if not results and configs:
                status = "FAIL"
                summary = "No nodes were available to receive configurations."
            else:
                status = (
                    "PASS" if all(v == "Success" for v in results.values()) else "FAIL"
                )
                car = (
                    (accepted_commands / total_commands) if total_commands > 0 else 0.0
                )
                summary = f"Tier 3 GNS3 validation complete. CAR: {car*100:.1f}%"
                if status == "FAIL":
                    failed_nodes = [k for k, v in results.items() if v != "Success"]
                    summary = f"GNS3 Validation failed for: {', '.join(failed_nodes)}. "
                    if push_errors:
                        summary += f"Errors: {'; '.join(push_errors)}"

            # Check for Interoperability (Multi-vendor)
            vendors = (
                set(d.vendor.lower() for d in devices if d.vendor) if devices else set()
            )
            is_multi_vendor = len(vendors) > 1

            return {
                "status": status,
                "tier": 3,
                "car": car if "car" in locals() else 0.0,
                "total_commands": total_commands,
                "accepted_commands": accepted_commands,
                "telnet_logs": telnet_logs,
                "is_multi_vendor": is_multi_vendor,
                "project_id": self.project_id,
                "nodes": nodes,
                "config_results": results,
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"Tier 3 validation failed: {e}")
            return {
                "status": "ERROR",
                "tier": 3,
                "error": str(e),
                "summary": f"Tier 3 GNS3 validation error: {str(e)}",
            }

    def push_configs(
        self, nodes: Dict[str, str], configs: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Pushes configurations to a set of nodes.
        """
        results = {}
        for device_name, config in configs.items():
            if device_name in nodes:
                logger.info(f"Pushing config to {device_name}...")
                node_stats = self._push_config_to_node(nodes[device_name], config)
                results[device_name] = (
                    "Success"
                    if node_stats["accepted"] == node_stats["total"]
                    and node_stats["total"] > 0
                    else "Failed"
                )
        return results

    def verify_functional(
        self, nodes: Dict[str, str], verification_data: Dict[str, List[str]]
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
                resp = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                    auth=self.auth,
                )
                node_info = resp.json()
                console_port = node_info.get("console")
                console_host = node_info.get("console_host", "localhost")
                if console_host == "0.0.0.0":
                    console_host = self.host

                with socket.create_connection((console_host, console_port), timeout=5):
                    tn = telnetlib.Telnet(console_host, console_port, timeout=5)

                    outputs = []
                    # Wake up
                    tn.write(b"\r\n")
                    time.sleep(0.5)

                    for cmd in commands:
                        tn.write(cmd.encode("ascii") + b"\r\n")
                        # Wait until prompt appears
                        idx, match, text = tn.expect([b">", b"#"], timeout=10)  # type: ignore
                        output = text.decode("ascii", errors="ignore")
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
        commands: List[str] = ["show ip route", "show ip interface brief"],
    ) -> Dict[str, Any]:
        """
        Captures a snapshot of the network state for Blast Radius analysis (Recommendation 3).
        """
        logger.info(f"Capturing network state baseline ({len(commands)} commands)...")
        state = {}

        for device_name, node_id in nodes.items():
            try:
                resp = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                    auth=self.auth,
                )
                node_info = resp.json()
                console_port = node_info.get("console")
                console_host = node_info.get("console_host", "localhost")
                if console_host == "0.0.0.0":
                    console_host = self.host

                with socket.create_connection((console_host, console_port), timeout=5):
                    tn = telnetlib.Telnet(console_host, console_port, timeout=5)

                    device_state = {}
                    # Wake up the console first
                    tn.write(b"\r\n\r\n")
                    time.sleep(1)
                    tn.read_very_eager()  # Clear buffer

                    for cmd in commands:
                        tn.write(cmd.encode("ascii") + b"\r\n")
                        # Wait for prompt to ensure command finished
                        try:
                            idx, match, text = tn.expect([b">", b"#"], timeout=5)  # type: ignore
                            output = text.decode("ascii", errors="ignore")

                            # Check for common CLI error indicators (Fix: Ensure functional check actually validates)
                            error_keywords = [
                                "Invalid input",
                                "Error:",
                                "Unknown command",
                                "Ambiguous command",
                                "syntax error",
                            ]
                            if any(
                                err.lower() in output.lower() for err in error_keywords
                            ):
                                device_state[cmd] = f"ERROR: {output.strip()}"
                            else:
                                device_state[cmd] = output
                        except Exception:
                            device_state[cmd] = "TIMEOUT: No prompt received"

                    tn.close()
                    state[device_name] = device_state
            except Exception as e:
                logger.error(f"State capture failed for {device_name}: {e}")

        return state

    def _wait_for_nodes_boot(self, nodes: Dict[str, str], timeout: int = 300) -> bool:
        """
        Polls the console of all nodes until a prompt is detected.
        Returns True if all nodes are ready, False if timeout reached.
        """
        start_time = time.time()
        pending_nodes = list(nodes.keys())

        logger.info(
            f"Polling console for {len(pending_nodes)} nodes (timeout: {timeout}s)..."
        )

        while time.time() - start_time < timeout and pending_nodes:
            for node_name in list(pending_nodes):
                node_id = nodes[node_name]
                try:
                    # Get console info
                    resp = requests.get(
                        f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                        auth=self.auth,
                    )
                    if resp.status_code != 200:
                        continue

                    node_info = resp.json()
                    console_port = node_info.get("console")
                    console_host = node_info.get("console_host", "localhost")
                    if console_host == "0.0.0.0":
                        console_host = self.host

                    if not console_port:
                        continue

                    # Try a non-blocking Telnet check
                    with socket.create_connection(
                        (console_host, console_port), timeout=2
                    ):
                        tn = telnetlib.Telnet(console_host, console_port, timeout=2)
                        tn.write(b"\r\n")
                        # Look for common prompts: Router>, Router#, Switch>, user:, login:
                        # Also handle Cisco "initial configuration dialog" [yes/no]
                        idx, match, text = tn.expect(
                            cast(
                                Any,
                                [
                                    b">",
                                    b"#",
                                    b"login:",
                                    b"user:",
                                    b"initial configuration dialog\? \[yes/no\]:",
                                ],
                            ),
                            timeout=5,
                        )

                        if idx == 4:
                            # Cisco Initial Config Dialog - say 'no'
                            logger.info(
                                f"Node {node_name} is in initial config dialog. Sending 'no'..."
                            )
                            tn.write(b"no\r\n")
                            time.sleep(1)
                            tn.write(b"\r\n")
                            # Don't remove from pending yet, wait for real prompt in next poll

                        elif idx != -1:
                            logger.info(f"Node {node_name} is READY (detected prompt)")
                            pending_nodes.remove(node_name)

                        tn.close()
                except (ConnectionRefusedError, socket.timeout, EOFError):
                    # Still booting
                    continue
                except Exception as e:
                    logger.debug(f"Polling error for {node_name}: {e}")
                    continue

            if pending_nodes:
                time.sleep(2)  # Wait between polls

        return len(pending_nodes) == 0

    def _get_or_create_project(self, name: str) -> str:
        """Finds existing project by name or creates a new one."""
        resp = requests.get(f"{self.base_url}/projects", auth=self.auth)
        if resp.status_code == 200:
            for p in resp.json():
                if p.get("name") == name:
                    # Open the project if it's closed
                    if p.get("status") != "opened":
                        requests.post(
                            f"{self.base_url}/projects/{p['project_id']}/open",
                            auth=self.auth,
                        )
                    return p["project_id"]

        return self._create_project(name)

    def _cleanup_project(self):
        """Deletes all nodes and links in the current project for a clean slate."""
        if not self.project_id:
            return

        # 1. Stop all nodes first (can't delete running nodes easily in some versions)
        logger.info("Stopping all nodes for cleanup...")
        try:
            requests.post(
                f"{self.base_url}/projects/{self.project_id}/nodes/stop",
                json={},
                auth=self.auth,
            )
            time.sleep(5)  # Increased wait for nodes to stop
        except Exception:
            pass

        # 2. Delete nodes with more retries and longer backoff
        max_retries = 5
        for attempt in range(max_retries):
            nodes_resp = requests.get(
                f"{self.base_url}/projects/{self.project_id}/nodes", auth=self.auth
            )
            if nodes_resp.status_code != 200:
                break

            nodes = nodes_resp.json()
            if not nodes:
                break

            for node in nodes:
                try:
                    requests.delete(
                        f"{self.base_url}/projects/{self.project_id}/nodes/{node['node_id']}",
                        auth=self.auth,
                    )
                except Exception as e:
                    logger.debug(
                        f"Retry {attempt+1}: Failed to delete node {node['node_id']}: {e}"
                    )

            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # More aggressive backoff

        # 3. Final verification
        verify = requests.get(
            f"{self.base_url}/projects/{self.project_id}/nodes", auth=self.auth
        )
        if verify.status_code == 200 and verify.json():
            logger.error(
                f"Cleanup incomplete for project {self.project_id} - stale nodes remain: {len(verify.json())}"
            )
            raise RuntimeError(
                f"GNS3 state not clean for validation in project {self.project_id}. "
                "Please manually clear the project or restart the GNS3 server if this persists."
            )

        logger.info("Project workspace cleared.")

    def _create_project(self, name: str) -> str:
        payload = {"name": name}
        resp = requests.post(f"{self.base_url}/projects", json=payload, auth=self.auth)
        resp.raise_for_status()
        return resp.json()["project_id"]

    def _find_template_for_vendor(self, vendor: str) -> Optional[Dict]:
        """Finds a suitable template based on device vendor."""
        try:
            resp = requests.get(f"{self.base_url}/templates", auth=self.auth)
            if resp.status_code != 200:
                return None

            templates = resp.json()
            vendor = (vendor or "cisco").lower()

            if vendor == "juniper":
                keywords = ["junos", "vsrx", "vmx", "olive", "juniper", "vyos"]
            else:
                keywords = ["router", "iosv", "cisco", "csr1000v", "viou", "iol"]

            # 1. Try IOU type first (preferred for your setup)
            for tmpl in templates:
                if tmpl.get("template_type") == "iou" and any(
                    k in tmpl["name"].lower() for k in keywords
                ):
                    return tmpl

            # 2. Try Name matching
            for keyword in keywords:
                for tmpl in templates:
                    if keyword in tmpl["name"].lower():
                        return tmpl
            return None
        except Exception as e:
            logger.error(f"Error finding template for {vendor}: {e}")
            return None

    def _create_nodes(self, devices: List[Any]) -> Dict[str, str]:
        """Creates nodes and returns a map of name -> node_id"""
        node_map = {}
        self.last_errors = []

        for i, device in enumerate(devices):
            template = self._find_template_for_vendor(device.vendor)

            if template:
                payload = {
                    "name": device.name,
                    "compute_id": "local",
                    "x": i * 150,
                    "y": 0,
                }
                logger.info(
                    f"Instantiating {device.vendor} template: {template['name']} for {device.name}"
                )
                endpoint = f"{self.base_url}/projects/{self.project_id}/templates/{template['template_id']}"
                resp = requests.post(endpoint, json=payload, auth=self.auth)

                if resp.status_code == 201:
                    node_map[device.name] = resp.json()["node_id"]
                else:
                    err = f"Failed to create node {device.name}: {resp.status_code} {resp.text}"
                    logger.error(err)
                    self.last_errors.append(err)
            else:
                err = f"No {device.vendor} images found in GNS3. Skipping node {device.name}."
                logger.warning(err)
                self.last_errors.append(err)

        return node_map

    def _create_links(self, node_map: Dict[str, str], intent: StructuredIntent) -> None:
        """Linear linking using PortManager. Handles IOU (port-based) and Qemu (adapter-based)."""
        device_names = list(node_map.keys())
        for i in range(len(device_names) - 1):
            node_a_id = node_map[device_names[i]]
            node_b_id = node_map[device_names[i + 1]]

            # Fetch node info to determine link strategy
            try:
                node_a_info = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_a_id}",
                    auth=self.auth,
                ).json()
                node_b_info = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_b_id}",
                    auth=self.auth,
                ).json()

                # Strategy: IOU uses port_number on adapter 0.
                # Qemu/VyOS uses adapter_number with port_number 0.
                is_a_iou = node_a_info.get("node_type") == "iou"
                is_b_iou = node_b_info.get("node_type") == "iou"

                port_a = self.port_manager.get_free_port(node_a_id)
                port_b = self.port_manager.get_free_port(node_b_id)

                adapter_a = 0 if is_a_iou else port_a
                p_num_a = port_a if is_a_iou else 0

                adapter_b = 0 if is_b_iou else port_b
                p_num_b = port_b if is_b_iou else 0

                payload = {
                    "nodes": [
                        {
                            "node_id": node_a_id,
                            "adapter_number": adapter_a,
                            "port_number": p_num_a,
                        },
                        {
                            "node_id": node_b_id,
                            "adapter_number": adapter_b,
                            "port_number": p_num_b,
                        },
                    ]
                }
                resp = requests.post(
                    f"{self.base_url}/projects/{self.project_id}/links",
                    json=payload,
                    auth=self.auth,
                )
                if resp.status_code not in [200, 201]:
                    err = f"Failed to create link between {device_names[i]} and {device_names[i+1]}: {resp.text}"
                    logger.error(err)
                    if hasattr(self, "last_errors"):
                        self.last_errors.append(err)
            except Exception as e:
                logger.error(
                    f"Error creating link between {device_names[i]} and {device_names[i+1]}: {e}"
                )

    def _push_config_to_node(
        self, node_id: str, config: str, vendor: str = "cisco"
    ) -> Dict[str, Any]:
        """Pushes configuration via Telnet and tracks command acceptance."""
        stats: Dict[str, Any] = {
            "total": 0,
            "accepted": 0,
            "telnet_log": [],
            "error": None,
        }
        try:
            resp = requests.get(
                f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                auth=self.auth,
            )
            if resp.status_code != 200:
                stats["error"] = f"Failed to get node info: {resp.status_code}"
                return stats

            node_info = resp.json()
            console_port = node_info.get("console")
            console_host = node_info.get("console_host", "localhost")
            if console_host == "0.0.0.0":
                console_host = self.host

            if not console_port:
                stats["error"] = "Console port not assigned"
                return stats

            error_keywords = [
                "% Invalid input",
                "Error:",
                "Unknown command",
                "Ambiguous command",
                "syntax error",
                "Invalid command",
                "error: ",
            ]

            tn = telnetlib.Telnet(console_host, console_port, timeout=15)
            tn.write(b"\r\n")
            time.sleep(1)

            # Vendor-specific navigation
            if vendor == "juniper":
                # Check if we are already in CLI
                idx, match, text = tn.expect([b">", b"#", b"%"], timeout=5)  # type: ignore
                if idx == 2:  # at shell %
                    tn.write(b"cli\r\n")
                    tn.expect([b">"], timeout=5)  # type: ignore

                tn.write(b"configure\r\n")
                tn.expect([b"Entering configuration mode", b"#"], timeout=5)  # type: ignore
            else:
                # Cisco/Default
                # Try to wake up and see where we are
                tn.write(b"\r\n")
                idx, match, text = tn.expect([b">", b"#", b"(config)#"], timeout=5)  # type: ignore

                if idx == 0:  # at >
                    tn.write(b"enable\r\n")
                    tn.expect([b"#"], timeout=5)  # type: ignore

                if idx != 2:  # not in config mode
                    tn.write(b"configure terminal\r\n")
                    tn.expect([b"(config)#", b"#"], timeout=10)  # type: ignore

            for line in config.splitlines():
                cmd = line.strip()
                if not cmd or cmd.startswith("!") or cmd.startswith("#"):
                    continue

                stats["total"] += 1
                tn.write(cmd.encode("ascii") + b"\r\n")

                # Check for errors after each command
                # Junos uses # as prompt in config mode, Cisco uses (config)#
                idx, match, text = tn.expect([b"(config)#", b"#", b">"], timeout=10)  # type: ignore
                output = text.decode("ascii", errors="ignore")

                accepted = not any(
                    err.lower() in output.lower() for err in error_keywords
                )
                if accepted:
                    stats["accepted"] += 1
                else:
                    err_msg = f"Rejected: {cmd} | Output: {output.strip()}"
                    logger.warning(f"GNS3 Reject ({vendor}): {err_msg}")
                    if stats["error"] is None:
                        stats["error"] = err_msg
                    else:
                        # Keep only first few errors to avoid bloated summary
                        if stats["error"].count(";") < 3:
                            stats["error"] += f"; {err_msg}"
                # Deep Trace: Log everything
                stats["telnet_log"].append(
                    {"command": cmd, "output": output.strip(), "accepted": accepted}
                )

            if vendor == "juniper":
                tn.write(b"commit and-quit\r\n")
                tn.expect([b"commit complete", b">"], timeout=30)  # type: ignore
            else:
                tn.write(b"end\r\n")
                tn.write(b"write memory\r\n")
                tn.expect([b"[OK]", b"#"], timeout=15)  # type: ignore

            tn.close()

            return stats
        except Exception as e:
            logger.error(f"Config push failed for {vendor} node {node_id}: {e}")
            stats["error"] = str(e)
            return stats
