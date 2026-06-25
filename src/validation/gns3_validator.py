import warnings

# Suppress telnetlib deprecation warning (slated for removal in Python 3.13)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telnetlib")

import logging  # noqa: E402
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

logger = setup_logger("GNS3Validator", level=logging.DEBUG)


def _run_async(coro):
    """
    Safely run an async coroutine from synchronous code.

    ``asyncio.run()`` creates a *new* event loop and tears it down when done.
    When called a second time in the same OS thread (e.g. after boot-polling
    already closed one loop), Python 3.11 raises:
        RuntimeError: cannot schedule new futures after shutdown
    We avoid this by always creating a fresh loop explicitly.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


class AsyncTelnet:
    """An asynchronous Telnet-like client for GNS3 console connection."""

    def __init__(self, host: str, port: int, timeout: float = 15.0, max_attempts: int = 5) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)  # at least 1 attempt
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.buffer = bytearray()
        self._lock = asyncio.Lock()  # Serialize console interactions
        self._semaphore = asyncio.Semaphore(5)  # Limit concurrent console sessions

    async def connect(self) -> None:
        """Open a TCP connection to the GNS3 console port.

        Uses ``self.max_attempts`` retries with exponential back-off.
        Boot-polling probes pass ``max_attempts=1`` so they fail-fast
        and let the outer polling loop decide when to retry.
        """
        for attempt in range(1, self.max_attempts + 1):
            logger.debug(
                f"AsyncTelnet connecting to {self.host}:{self.port} "
                f"(attempt {attempt}/{self.max_attempts})"
            )
            try:
                try:
                    self.reader, self.writer = await asyncio.wait_for(
                        asyncio.open_connection(self.host, self.port), timeout=self.timeout
                    )
                except OSError as e:
                    # Fall back to explicit IPv4 only when:
                    #  - the host was not already an IPv4 literal, AND
                    #  - the OSError is an aggregate (errno=None) suggesting an
                    #    IPv6/IPv4 dual-stack resolution failure, not a plain refuse.
                    if self.host not in ("127.0.0.1", "localhost") and e.errno is None:
                        logger.debug(
                            f"Dual-stack connect to {self.host}:{self.port} failed: {e}; "
                            "retrying with explicit 127.0.0.1"
                        )
                        self.reader, self.writer = await asyncio.wait_for(
                            asyncio.open_connection("127.0.0.1", self.port), timeout=self.timeout
                        )
                    else:
                        # Hard refusal (ECONNREFUSED) – console not ready yet.
                        # Re-raise so the except block below can handle retry logic.
                        raise
                self.buffer = bytearray()
                logger.debug(
                    f"AsyncTelnet connected to {self.host}:{self.port} on attempt {attempt}"
                )
                return
            except (ConnectionRefusedError, OSError) as e:
                logger.debug(
                    f"AsyncTelnet attempt {attempt}/{self.max_attempts} "
                    f"to {self.host}:{self.port} failed: {e}"
                )
                if attempt == self.max_attempts:
                    raise
                backoff = min(2 ** attempt, 10)
                logger.debug(f"Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
            except Exception as e:
                logger.exception(
                    f"AsyncTelnet unexpected error on attempt {attempt}/{self.max_attempts}: {e}"
                )
                if attempt == self.max_attempts:
                    raise
                await asyncio.sleep(min(2 ** attempt, 10))

    async def write(self, data: bytes) -> None:
        async with self._lock:
            if self.writer:
                logger.debug(f"Writing {len(data)} bytes to console.")
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
        logger.debug(f"Expect called with {len(list_of_bytes)} patterns, timeout={timeout}")
        async with self._lock:
            if not self.reader:
                logger.debug("No reader available, returning failure.")
                return -1, None, b""

            start_time = asyncio.get_event_loop().time()
            while True:
                # Check buffer first
                for idx, pattern in enumerate(list_of_bytes):
                    match = re.search(pattern, self.buffer)
                    if match:
                        end_idx = match.end()
                        matched_chunk = bytes(self.buffer[:end_idx])
                        self.buffer = self.buffer[end_idx:]
                        logger.debug(f"Pattern {idx} matched, returning data of length {len(matched_chunk)}")
                        return idx, match, matched_chunk

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.debug(f"Expect timeout after {elapsed}s, returning buffered data length {len(self.buffer)}")
                    return -1, None, bytes(self.buffer)

                # Read more data with a short timeout
                try:
                    remaining = max(0.0, timeout - elapsed)
                    chunk = await asyncio.wait_for(
                        self.reader.read(1024), timeout=min(1.0, remaining)
                    )
                    if not chunk:
                        logger.debug("Reader returned empty chunk, connection closed.")
                        return -1, None, bytes(self.buffer)
                    self.buffer.extend(chunk)
                    logger.debug(f"Read {len(chunk)} bytes, buffer size now {len(self.buffer)}")
                except asyncio.TimeoutError:
                    logger.debug("Read timeout, continue loop.")
                    continue
                except Exception as e:
                    logger.exception(f"Unexpected error in expect: {e}")
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
        self._semaphore = asyncio.Semaphore(5)  # Limit concurrent console sessions

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
        # Ensure each config block is grounded with a source reference
        for cfg_name, cfg in configs.items():
            if isinstance(cfg, dict) and cfg.get("source_id") is None:
                logger.warning(f"Config '{cfg_name}' missing source_id; skipping validation for this block.")
                configs.pop(cfg_name, None)

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
                    logger.exception("Failed to delete previous GNS3 project")
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

            # ── L2-only guard ────────────────────────────────────────────────
            # IOU Router (the only template in this GNS3 setup) is an L3 image.
            # Pure L2 commands (switchport, vlan database, dhcp snooping, etc.)
            # will be rejected by the IOU router with "Invalid input".
            # Detect this case early and return SKIPPED (infrastructure gap)
            # rather than a misleading FAIL.
            all_config_cmds = " ".join(
                line.strip()
                for cfg in configs.values()
                for line in (cfg.splitlines() if isinstance(cfg, str) else [])
                if line.strip() and not line.strip().startswith(("!", "#"))
            ).lower()

            L2_ONLY_SIGNALS = [
                "switchport mode",
                "switchport trunk",
                "switchport access",
                "ip dhcp snooping vlan",
                "spanning-tree vlan",
                "vlan database",
                "channel-group",
            ]
            # Also detect bare 'vlan <number>' lines (VLAN creation in global config)
            import re as _re
            def _is_l2_line(line: str) -> bool:
                l = line.lower()
                if any(sig in l for sig in L2_ONLY_SIGNALS):
                    return True
                # 'vlan 100' or 'vlan 10,20,30' at start of line = L2 global config
                if _re.match(r'^vlan\s+[\d,]+\s*$', l):
                    return True
                return False
            # Count how many lines look like pure L2 vs total
            cmd_lines = [
                l.strip() for cfg in configs.values()
                for l in (cfg.splitlines() if isinstance(cfg, str) else [])
                if l.strip() and not l.strip().startswith(("!", "#"))
            ]
            l2_lines = sum(
                1 for l in cmd_lines
                if _is_l2_line(l)
            )
            # Adaptive threshold: short configs (≤10 lines) need only 1 L2 line;
            # longer configs need ≥33% L2 lines to avoid false-positive skips
            # on mixed L2/L3 configs (e.g., OSPF + a trunk port).
            if cmd_lines and l2_lines > 0:
                threshold = 0.33
                if len(cmd_lines) <= 10:
                    threshold = 1 / len(cmd_lines)  # any single L2 line triggers SKIPPED
                is_l2_only = (l2_lines / len(cmd_lines)) >= threshold
            else:
                is_l2_only = False

            if is_l2_only:
                skip_msg = (
                    "GNS3 SKIPPED: Config contains predominantly L2 switch commands "
                    f"({l2_lines}/{len(cmd_lines)} lines) which are not supported by the "
                    "IOU Router template. An IOU-L2 image is required for full L2 validation."
                )
                logger.warning(skip_msg)
                return {
                    "status": "SKIPPED",
                    "tier": 3,
                    "car": None,
                    "total_commands": 0,
                    "accepted_commands": 0,
                    "summary": skip_msg,
                }

            # ─────────────────────────────────────────────────────────────────

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

            # Intelligent Polling: Wait for nodes to reach a ready state (max 90s)
            boot_success = self._wait_for_nodes_boot(nodes)
            if not boot_success:
                # Nodes failed to boot — proceeding to config push would hang on
                # the same dead console ports. Fail fast with a clear message.
                failed_nodes = list(nodes.keys())
                err_msg = (
                    f"GNS3 nodes did not boot within timeout: {', '.join(failed_nodes)}. "
                    "Console port never opened — check that IOU/IOSv images are installed "
                    "and licensed on the GNS3 server."
                )
                logger.error(err_msg)
                return {
                    "status": "FAIL",
                    "tier": 3,
                    "car": 0.0,
                    "total_commands": 0,
                    "accepted_commands": 0,
                    "summary": err_msg,
                    "project_id": self.project_id,
                }

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

            node_stats_dict = _run_async(push_all())

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

        node_stats_dict = _run_async(push_all())
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
        # Limit concurrent console sessions to avoid GNS3 overload
        async with self._semaphore:
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

                tn = AsyncTelnet(console_host, console_port, timeout=5, max_attempts=2)
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
                logger.exception(f"Verification failed for {device_name}")
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

        return _run_async(verify_all())

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

            tn = AsyncTelnet(console_host, console_port, timeout=5, max_attempts=2)
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

        return _run_async(capture_all())

    async def _wait_for_single_node_boot_async(
        self, node_name: str, node_id: str, timeout: int
    ) -> bool:
        """
        Wait for a single GNS3 node console to become ready.

        Strategy:
        1. Poll the GNS3 REST API every 2s to check the node ``status``.
           If the status never reaches ``started`` within *timeout*, bail out.
        2. Once the node is ``started`` in GNS3, give the OS up to 60s to open
           the console TCP port.  If the port stays ECONNREFUSED after that
           window, the IOU image is broken / not licensed — fail fast rather
           than spinning for the full timeout.
        """
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        console_open_deadline: Optional[float] = None  # set once node is "started"

        while loop.time() - start_time < timeout:
            elapsed = loop.time() - start_time
            try:
                resp = requests.get(
                    f"{self.base_url}/projects/{self.project_id}/nodes/{node_id}",
                    auth=self.auth,
                    timeout=5,
                )
                if resp.status_code != 200:
                    await asyncio.sleep(2)
                    continue

                node_info = resp.json()
                node_status = node_info.get("status", "stopped")
                console_port = node_info.get("console")
                console_host = node_info.get("console_host", "localhost")
                if console_host == "0.0.0.0":
                    console_host = self.host

                # ── Stage 1: wait for GNS3 to report the node as started ─────
                if node_status != "started":
                    logger.debug(
                        f"Node {node_name} status={node_status!r} (elapsed {elapsed:.0f}s) – waiting"
                    )
                    await asyncio.sleep(2)
                    continue

                if not console_port:
                    await asyncio.sleep(2)
                    continue

                # ── Stage 2: node is started – set a 60s console-open deadline ─
                if console_open_deadline is None:
                    console_open_deadline = loop.time() + 60
                    logger.info(
                        f"Node {node_name} is started; waiting up to 60s for console "
                        f"{console_host}:{console_port}"
                    )

                if loop.time() > console_open_deadline:
                    logger.warning(
                        f"Node {node_name}: console {console_host}:{console_port} never opened "
                        "after 60s — IOU image may be missing or unlicensed. Giving up."
                    )
                    return False

                # ── Stage 3: try to open the console TCP connection ───────────
                try:
                    tn = AsyncTelnet(console_host, console_port, timeout=2, max_attempts=1)
                    await tn.connect()
                    await tn.write(b"\r\n")

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
                except (ConnectionRefusedError, OSError, asyncio.TimeoutError, socket.timeout):
                    # Console port not open yet – normal during early boot
                    pass

            except Exception as e:
                logger.debug(f"Boot-poll error for {node_name}: {e}")

            await asyncio.sleep(2)

        logger.warning(f"Node {node_name} boot-poll timed out after {timeout}s")
        return False

    def _wait_for_nodes_boot(self, nodes: Dict[str, str], timeout: int = 90) -> bool:
        """
        Polls the console of all nodes concurrently until a prompt is detected.
        Returns True if ALL nodes booted successfully, False otherwise.
        Timeout reduced to 90s: IOU nodes should boot within 60s;
        if they don't the image is likely broken and we should bail fast.
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

        return _run_async(poll_all())

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

    # Template types that have a real IOS console and can accept CLI commands
    _CONSOLE_TEMPLATE_TYPES = {"iou", "qemu", "dynamips", "docker"}

    def _find_template_for_vendor(
        self,
        vendor: str,
        device_name: str = "",
        intent: Optional[StructuredIntent] = None,
    ) -> Optional[Dict]:
        """Finds a suitable GNS3 template that has a real IOS/CLI console.

        Priority:
        1. IOU templates (Router/IOS) — always preferred; support both L2 and L3 commands.
        2. Qemu templates (vSRX, IOSv) — for Juniper or when IOU not available.
        3. Built-in switch/hub types (ethernet_switch, ethernet_hub) are NEVER returned
           because they have no console and cannot accept CLI commands.
        """
        try:
            resp = requests.get(f"{self.base_url}/templates", auth=self.auth)
            if resp.status_code != 200:
                return None

            templates = resp.json()

            # Filter to only templates that have a real console
            console_templates = [
                t for t in templates
                if t.get("template_type") in self._CONSOLE_TEMPLATE_TYPES
            ]

            vendor = (vendor or "cisco").lower()

            if vendor == "juniper":
                # Juniper: prefer qemu vSRX; fall back to any qemu
                keywords = ["vsrx", "vmx", "olive", "juniper", "junos", "vyos"]
                for tmpl in console_templates:
                    if any(k in tmpl["name"].lower() for k in keywords):
                        return tmpl
                return None

            # Cisco / generic: IOU is the best match (supports both L2 and L3 commands)
            # Prefer the template literally named 'Router' or 'IOS' first.
            preferred_names = ["router", "ios"]
            for tmpl in console_templates:
                if tmpl.get("template_type") == "iou" and any(
                    tmpl["name"].lower() == n for n in preferred_names
                ):
                    logger.debug(
                        f"Template match for {device_name!r} (vendor={vendor}): "
                        f"{tmpl['name']!r} (IOU)"
                    )
                    return tmpl

            # Fall back to any IOU template
            for tmpl in console_templates:
                if tmpl.get("template_type") == "iou":
                    logger.debug(
                        f"Template fallback for {device_name!r}: {tmpl['name']!r} (IOU)"
                    )
                    return tmpl

            # Last resort: any qemu template with cisco-sounding name
            for tmpl in console_templates:
                if tmpl.get("template_type") == "qemu" and any(
                    k in tmpl["name"].lower() for k in ["iosv", "csr", "cisco"]
                ):
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
