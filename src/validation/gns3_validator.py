import warnings

# Suppress telnetlib deprecation warning (slated for removal in Python 3.13)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telnetlib")

import requests  # noqa: E402
import time  # noqa: E402
import socket  # noqa: E402
import os  # noqa: E402
import asyncio  # noqa: E402
import re  # noqa: E402
import uuid  # noqa: E402

# noqa: E402
from typing import Dict, Any, List, Optional  # noqa: E402

# noqa: E402
from src.validation.base import NetworkValidator  # noqa: E402
from src.config import settings  # noqa: E402
from src.utils import setup_logger  # noqa: E402
from src.schemas.intent import StructuredIntent  # noqa: E402

logger = setup_logger("GNS3Validator")


class AsyncTelnet:
    """An asynchronous Telnet-like client for GNS3 console connection."""

    def __init__(self, host: str, port: int, timeout: float = 15.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.buffer = bytearray()

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
        )
        self.buffer = bytearray()

    async def write(self, data: bytes) -> None:
        if self.writer:
            self.writer.write(data)
            await self.writer.drain()

    async def read_very_eager(self) -> bytes:
        if not self.reader:
            return b""
        try:
            return await asyncio.wait_for(self.reader.read(4096), timeout=0.01)
        except asyncio.TimeoutError:
            return b""
        except Exception:
            return b""

    async def expect(
        self, list_of_bytes: List[bytes], timeout: float = 10.0
    ) -> tuple[int, Optional[re.Match], bytes]:
        """
        Reads from reader until one of the regex byte patterns matches,
        or timeout is reached.
        Returns: (matched_index, match_object, accumulated_bytes)
        """
        if not self.reader:
            return -1, None, b""

        start_time = asyncio.get_event_loop().time()
        while True:
            # Check buffer first
            for idx, pattern in enumerate(list_of_bytes):
                # Search using regex over self.buffer
                match = re.search(pattern, self.buffer)
                if match:
                    end_idx = match.end()
                    matched_chunk = bytes(self.buffer[:end_idx])
                    self.buffer = self.buffer[end_idx:]
                    return idx, match, matched_chunk

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                return -1, None, bytes(self.buffer)

            # Read more data with a short timeout
            try:
                chunk = await asyncio.wait_for(
                    self.reader.read(1024), timeout=min(1.0, timeout - elapsed)
                )
                if not chunk:
                    # Connection closed
                    return -1, None, bytes(self.buffer)
                self.buffer.extend(chunk)
            except asyncio.TimeoutError:
                continue
            except Exception:
                return -1, None, bytes(self.buffer)

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass


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
            os.getenv("GNS3_USERNAME", "admin"),
            os.getenv(
                "GNS3_PASSWORD",
                "ZQMSdXR6LVD5rN7gx2ipegzMYPYOZJeo7IJviL87PjgvYK4p8bg1R1fT9YgOTzX9",
            ),
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

    def __del__(self):
        """Cleanup GNS3 project on destruction."""
        if hasattr(self, "project_id") and self.project_id:
            try:
                self._cleanup_project()
                requests.delete(
                    f"{self.base_url}/projects/{self.project_id}", auth=self.auth
                )
                logger.info(
                    f"Deleted temporary GNS3 project {self.project_id} on destruction."
                )
            except Exception:
                pass

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
            # 1. Cleanup previous project if it exists in this session to free resources
            if self.project_id:
                try:
                    self._cleanup_project()
                    requests.delete(
                        f"{self.base_url}/projects/{self.project_id}", auth=self.auth
                    )
                    logger.info(f"Deleted previous GNS3 project {self.project_id}")
                except Exception as e:
                    logger.warning(f"Error deleting previous GNS3 project: {e}")
                self.project_id = None

            # 2. Create dynamic Project
            project_name = f"RAG_NetTwin_DigitalTwin_{uuid.uuid4().hex[:8]}"
            self.project_id = self._get_or_create_project(project_name)
            logger.info(
                f"Using dynamic GNS3 project: {project_name} ({self.project_id})"
            )

            # 3. Cleanup
            self._cleanup_project()

            # 3. Build Topology
            devices = intent.devices if intent else []
            nodes = self._create_nodes(devices, intent)
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

            # 4. Push Configs & Track Stats (Recommendation CAR) concurrently
            async def push_all():
                tasks = []
                device_names = []
                for device_name, config in configs.items():
                    if device_name in nodes:
                        vendor = "cisco"
                        if intent and intent.devices:
                            for dev in intent.devices:
                                if dev.name == device_name:
                                    vendor = (dev.vendor or "cisco").lower()
                                    break
                        device_names.append(device_name)
                        tasks.append(
                            self._push_config_to_node(
                                nodes[device_name], config, vendor
                            )
                        )
                results_list = await asyncio.gather(*tasks)
                return dict(zip(device_names, results_list))

            node_stats_dict = asyncio.run(push_all())

            results = {}
            total_commands = 0
            accepted_commands = 0
            telnet_logs = {}
            push_errors = []

            for device_name, node_stats in node_stats_dict.items():
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
                summary = f"Tier 3 GNS3 validation complete. CAR: {car * 100:.1f}%"
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
        Pushes configurations to a set of nodes concurrently.
        """
        results = {}

        async def push_all():
            tasks = []
            device_names = []
            for device_name, config in configs.items():
                if device_name in nodes:
                    device_names.append(device_name)
                    tasks.append(self._push_config_to_node(nodes[device_name], config))
            results_list = await asyncio.gather(*tasks)
            return dict(zip(device_names, results_list))

        node_stats_dict = asyncio.run(push_all())
        for device_name, node_stats in node_stats_dict.items():
            results[device_name] = (
                "Success"
                if node_stats["accepted"] == node_stats["total"]
                and node_stats["total"] > 0
                else "Failed"
            )
        return results

    async def _verify_single_node_functional_async(
        self, device_name: str, node_id: str, commands: List[str]
    ) -> List[Dict[str, str]]:
        if not commands:
            return []
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

            tn = AsyncTelnet(console_host, console_port, timeout=5)
            await tn.connect()

            outputs = []
            await tn.write(b"\r\n")
            await asyncio.sleep(0.5)

            for cmd in commands:
                await tn.write(cmd.encode("ascii") + b"\r\n")
                idx, match, text = await tn.expect([b">", b"#"], timeout=10)
                output = text.decode("ascii", errors="ignore")
                outputs.append({"command": cmd, "output": output})

            await tn.close()
            return outputs
        except Exception as e:
            logger.error(f"Verification failed for {device_name}: {e}")
            return [{"error": str(e)}]

    def verify_functional(
        self, nodes: Dict[str, str], verification_data: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Closed-Loop Verification (Recommendation 1).
        Executes verification commands concurrently and returns output.
        """
        logger.info("Starting Functional Intent Verification concurrently...")
        # Wait for network convergence
        time.sleep(10)

        async def verify_all():
            tasks = []
            device_names = []
            for device_name, commands in verification_data.items():
                if device_name in nodes and commands:
                    device_names.append(device_name)
                    tasks.append(
                        self._verify_single_node_functional_async(
                            device_name, nodes[device_name], commands
                        )
                    )
            results = await asyncio.gather(*tasks)
            return dict(zip(device_names, results))

        return asyncio.run(verify_all())

    async def _get_single_node_network_state_async(
        self, device_name: str, node_id: str, commands: List[str]
    ) -> Dict[str, str]:
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

            tn = AsyncTelnet(console_host, console_port, timeout=5)
            await tn.connect()

            device_state = {}
            await tn.write(b"\r\n\r\n")
            await asyncio.sleep(1)
            await tn.read_very_eager()

            error_keywords = [
                "Invalid input",
                "Error:",
                "Unknown command",
                "Ambiguous command",
                "syntax error",
            ]

            for cmd in commands:
                await tn.write(cmd.encode("ascii") + b"\r\n")
                try:
                    idx, match, text = await tn.expect([b">", b"#"], timeout=5)
                    output = text.decode("ascii", errors="ignore")

                    if any(err.lower() in output.lower() for err in error_keywords):
                        device_state[cmd] = f"ERROR: {output.strip()}"
                    else:
                        device_state[cmd] = output
                except Exception:
                    device_state[cmd] = "TIMEOUT: No prompt received"

            await tn.close()
            return device_state
        except Exception as e:
            logger.error(f"State capture failed for {device_name}: {e}")
            return {"error": str(e)}

    def get_network_state(
        self,
        nodes: Dict[str, str],
        commands: List[str] = ["show ip route", "show ip interface brief"],
    ) -> Dict[str, Any]:
        """
        Captures a snapshot of the network state for Blast Radius analysis (Recommendation 3) concurrently.
        """
        logger.info(
            f"Capturing network state baseline concurrently ({len(commands)} commands)..."
        )

        async def capture_all():
            tasks = []
            device_names = []
            for device_name, node_id in nodes.items():
                device_names.append(device_name)
                tasks.append(
                    self._get_single_node_network_state_async(
                        device_name, node_id, commands
                    )
                )
            results = await asyncio.gather(*tasks)
            return dict(zip(device_names, results))

        return asyncio.run(capture_all())

    async def _wait_for_single_node_boot_async(
        self, node_name: str, node_id: str, timeout: int
    ) -> bool:
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                resp = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                    auth=self.auth,
                )
                if resp.status_code != 200:
                    await asyncio.sleep(2)
                    continue

                node_info = resp.json()
                console_port = node_info.get("console")
                console_host = node_info.get("console_host", "localhost")
                if console_host == "0.0.0.0":
                    console_host = self.host

                if not console_port:
                    await asyncio.sleep(2)
                    continue

                tn = AsyncTelnet(console_host, console_port, timeout=2)
                await tn.connect()
                await tn.write(b"\r\n")

                # Look for common prompts: Router>, Router#, Switch>, user:, login:
                # Also handle Cisco "initial configuration dialog" [yes/no]
                idx, match, text = await tn.expect(
                    [
                        b">",
                        b"#",
                        b"login:",
                        b"user:",
                        rb"initial configuration dialog\? \[yes/no\]:",
                    ],
                    timeout=5,
                )

                if idx == 4:
                    logger.info(
                        f"Node {node_name} is in initial config dialog. Sending 'no'..."
                    )
                    await tn.write(b"no\r\n")
                    await asyncio.sleep(1)
                    await tn.write(b"\r\n")
                elif idx != -1:
                    logger.info(f"Node {node_name} is READY (detected prompt)")
                    await tn.close()
                    return True

                await tn.close()
            except (
                ConnectionRefusedError,
                socket.timeout,
                asyncio.TimeoutError,
                OSError,
            ):
                # Still booting
                pass
            except Exception as e:
                logger.debug(f"Polling error for {node_name}: {e}")

            await asyncio.sleep(2)
        return False

    def _wait_for_nodes_boot(self, nodes: Dict[str, str], timeout: int = 300) -> bool:
        """
        Polls the console of all nodes concurrently until a prompt is detected.
        Returns True if all nodes are ready, False if timeout reached.
        """
        logger.info(
            f"Polling console for {len(nodes)} nodes concurrently (timeout: {timeout}s)..."
        )

        async def poll_all():
            tasks = [
                self._wait_for_single_node_boot_async(name, nid, timeout)
                for name, nid in nodes.items()
            ]
            results = await asyncio.gather(*tasks)
            return all(results)

        return asyncio.run(poll_all())

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
                        f"Retry {attempt + 1}: Failed to delete node {node['node_id']}: {e}"
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

    def _find_template_for_vendor(
        self,
        vendor: str,
        device_name: str = "",
        intent: Optional[StructuredIntent] = None,
    ) -> Optional[Dict]:
        """Finds a suitable template based on device vendor and L2/L3 intent properties."""
        try:
            resp = requests.get(f"{self.base_url}/templates", auth=self.auth)
            if resp.status_code != 200:
                return None

            templates = resp.json()
            vendor = (vendor or "cisco").lower()
            device_name_lower = (device_name or "").lower()

            # Inspect intent or device name to determine if the target should be a Switch or a Router
            is_switch = False
            if any(
                sw_kw in device_name_lower
                for sw_kw in ["switch", "-sw", "sw-", "cat9", "catalyst"]
            ):
                is_switch = True

            if intent:
                proto_lower = (intent.protocol or "").lower()
                if any(
                    l2_kw in proto_lower
                    for l2_kw in [
                        "vlan",
                        "spanning-tree",
                        "switchport",
                        "lacp",
                        "etherchannel",
                    ]
                ):
                    is_switch = True

                params_str = str(intent.parameters).lower()
                if any(
                    l2_kw in params_str
                    for l2_kw in [
                        "switchport",
                        "vlan",
                        "trunk",
                        "access",
                        "spanning-tree",
                    ]
                ):
                    is_switch = True

            if vendor == "juniper":
                keywords = ["junos", "vsrx", "vmx", "olive", "juniper", "vyos"]
            else:
                if is_switch:
                    keywords = ["iosvl2", "switch", "l2", "viou-l2", "iol-l2", "cisco"]
                else:
                    keywords = ["router", "iosv", "csr1000v", "viou", "iol", "cisco"]

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

    def _create_nodes(
        self, devices: List[Any], intent: Optional[StructuredIntent] = None
    ) -> Dict[str, str]:
        """Creates nodes and returns a map of name -> node_id"""
        node_map = {}
        self.last_errors = []

        for i, device in enumerate(devices):
            template = self._find_template_for_vendor(
                device.vendor, device.name, intent
            )

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
                    err = f"Failed to create link between {device_names[i]} and {device_names[i + 1]}: {resp.text}"
                    logger.error(err)
                    if hasattr(self, "last_errors"):
                        self.last_errors.append(err)
            except Exception as e:
                logger.error(
                    f"Error creating link between {device_names[i]} and {device_names[i + 1]}: {e}"
                )

    async def _push_config_to_node(
        self, node_id: str, config: str, vendor: str = "cisco"
    ) -> Dict[str, Any]:
        """Pushes configuration asynchronously via AsyncTelnet and tracks command acceptance."""
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
                b"% Invalid input",
                b"Error:",
                b"Unknown command",
                b"Ambiguous command",
                b"syntax error",
                b"Invalid command",
                b"error: ",
            ]

            tn = AsyncTelnet(console_host, console_port, timeout=15)
            await tn.connect()
            await tn.write(b"\r\n")
            await asyncio.sleep(1)

            # Vendor-specific navigation
            if vendor == "juniper":
                # Check if we are already in CLI
                idx, match, text = await tn.expect([b">", b"#", b"%"], timeout=5)
                if idx == 2:  # at shell %
                    await tn.write(b"cli\r\n")
                    await tn.expect([b">"], timeout=5)

                await tn.write(b"configure\r\n")
                await tn.expect([b"Entering configuration mode", b"#"], timeout=5)
            else:
                # Cisco/Default
                # Try to wake up and see where we are
                await tn.write(b"\r\n")
                idx, match, text = await tn.expect(
                    [b">", b"#", rb"\(config\)#"], timeout=5
                )

                if idx == 0:  # at >
                    await tn.write(b"enable\r\n")
                    await tn.expect([b"#"], timeout=5)

                if idx != 2:  # not in config mode
                    await tn.write(b"configure terminal\r\n")
                    await tn.expect([rb"\(config\)#", b"#"], timeout=10)

            # Flush telnet buffer before entering command loop to discard stale prompts
            await asyncio.sleep(0.5)
            try:
                await tn.read_very_eager()
            except Exception:
                pass

            for line in config.splitlines():
                cmd = line.strip()
                if not cmd or cmd.startswith("!") or cmd.startswith("#"):
                    continue

                # Skip transition commands that the validator handles automatically
                if cmd.lower() in ["configure terminal", "config t", "enable"]:
                    continue

                stats["total"] += 1
                await tn.write(cmd.encode("ascii") + b"\r\n")

                # Check for errors after each command
                idx, match, text = await tn.expect(
                    [rb"\(config\)#", b"#", b">"], timeout=10
                )
                output = text.decode("ascii", errors="ignore")

                accepted = not any(
                    err.lower() in output.lower().encode("ascii", errors="ignore")
                    for err in error_keywords
                )

                if accepted:
                    stats["accepted"] += 1
                else:
                    err_msg = f"Rejected: {cmd} | Output: {output.strip()}"
                    logger.warning(f"GNS3 Reject ({vendor}): {err_msg}")
                    if stats["error"] is None:
                        stats["error"] = err_msg
                    else:
                        if stats["error"].count(";") < 3:
                            stats["error"] += f"; {err_msg}"
                stats["telnet_log"].append(
                    {"command": cmd, "output": output.strip(), "accepted": accepted}
                )

            if vendor == "juniper":
                await tn.write(b"commit and-quit\r\n")
                await tn.expect([b"commit complete", b">"], timeout=30)
            else:
                await tn.write(b"end\r\n")
                await tn.write(b"write memory\r\n")
                await tn.expect([rb"\[OK\]", b"#"], timeout=15)

            await tn.close()
            return stats
        except Exception as e:
            logger.error(f"Config push failed for {vendor} node {node_id}: {e}")
            stats["error"] = str(e)
            return stats
