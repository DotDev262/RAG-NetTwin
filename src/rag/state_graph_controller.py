"""
State-Invariant Graph Controller for RAG-NetTwin v2.

Upgrades the Network Master Plan into a centralized, state-aware graph controller
using NetworkX. Maintains global topology state and enforces innate parameter invariants
(OSPF Area IDs, MD5 authentication keys, BGP AS numbers, IP subnets) across multi-router
heterogeneous networks (Cisco IOS-XE and Juniper JunOS).
"""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Set
import networkx as nx
from pydantic import BaseModel, Field

from src.schemas.intent import StructuredIntent, DeviceIntent
from src.utils import setup_logger

logger = setup_logger("StateInvariantGraphController")


class LinkEndpoint(BaseModel):
    """Endpoint description of a physical or logical link on a device."""
    device_name: str
    interface_name: str
    ip_address: Optional[str] = None
    subnet: Optional[str] = None
    mtu: Optional[int] = 1500
    ospf_area: Optional[str] = None
    ospf_hello_interval: Optional[int] = None
    ospf_dead_interval: Optional[int] = None
    ospf_auth_key: Optional[str] = None


class NetworkLink(BaseModel):
    """Bidirectional connection between two network devices."""
    link_id: str
    node_a: LinkEndpoint
    node_b: LinkEndpoint
    shared_subnet: Optional[str] = None
    protocol: Optional[str] = None


class StateInvariant(BaseModel):
    """Enforced parameter invariant across network topology."""
    invariant_type: str  # e.g., "OSPF_AREA_MATCH", "SUBNET_CONSISTENCY", "BGP_PEERING"
    devices: List[str]
    parameters: Dict[str, Any]
    description: str
    mandatory: bool = True


class ConflictResolutionResult(BaseModel):
    """Report produced when intercepting and evaluating synthesized configurations."""
    has_conflicts: bool
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_prompt: Optional[str] = None


class StateInvariantGraphController:
    """
    Centralized graph controller that manages global network topology state
    and enforces parameter consistency across multi-router topologies during synthesis.
    """

    def __init__(self, registry_path: Optional[str] = None):
        self.graph = nx.Graph()
        self.registry_path = registry_path or "config/alignment_rules_registry.json"
        self._alignment_registry = None
        self._load_registry()

    def _load_registry(self):
        """Loads static alignment rules from the offline-compiled registry if available."""
        from pathlib import Path
        p = Path(self.registry_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    self._alignment_registry = json.load(f)
                logger.info(f"Loaded compile-time alignment rules registry from {p}")
            except Exception as e:
                logger.warning(f"Failed to load alignment rules registry: {e}")

    def build_topology_from_intent(self, intent: StructuredIntent) -> nx.Graph:
        """
        Builds or updates the centralized NetworkX graph representing the desired network topology.
        Extracts nodes, links, interfaces, and protocol bindings from the intent.
        """
        self.graph.clear()
        devices = intent.devices or []
        params = intent.parameters or {}
        protocol = (intent.protocol or "").lower()

        # Add nodes
        for dev in devices:
            self.graph.add_node(
                dev.name,
                vendor=(dev.vendor or "cisco").lower(),
                os_type=(dev.os_type or "ios-xe").lower(),
                os_version=dev.os_version or "17.6",
                protocol=protocol,
                parameters={},
            )

        # Infer or extract links between devices
        dev_names = [d.name for d in devices if d.name]
        
        # Check if explicit topology links or peers exist in params
        if "links" in params and isinstance(params["links"], list):
            for link in params["links"]:
                u = link.get("source") or link.get("node_a")
                v = link.get("target") or link.get("node_b")
                if u and v:
                    self.graph.add_edge(
                        u,
                        v,
                        subnet=link.get("subnet"),
                        interface_a=link.get("interface_a", "GigabitEthernet0/1"),
                        interface_b=link.get("interface_b", "GigabitEthernet0/1"),
                        protocol=protocol,
                        ospf_area=link.get("area", params.get("area", "0")),
                        auth_key=link.get("auth_key", params.get("auth_key") or params.get("password")),
                    )
        elif len(dev_names) == 2:
            # Standard point-to-point adjacency between the two devices
            dev_a, dev_b = dev_names[0], dev_names[1]
            subnet = params.get("subnet") or params.get("network")
            if not subnet and "ip" in params:
                # If IP provided like 192.168.1.1/24 or 10.1.1.1/30, derive link subnet
                try:
                    ip_net = ipaddress.ip_network(params["ip"], strict=False)
                    subnet = str(ip_net)
                except Exception:
                    subnet = "10.0.0.0/30"
            elif not subnet:
                subnet = "10.0.0.0/30"

            self.graph.add_edge(
                dev_a,
                dev_b,
                subnet=subnet,
                interface_a=params.get("interface_a") or params.get("interface", "GigabitEthernet0/1"),
                interface_b=params.get("interface_b") or params.get("interface", "GigabitEthernet0/1"),
                protocol=protocol,
                ospf_area=params.get("area", "0"),
                hello_interval=params.get("hello_interval") or params.get("hello_timer"),
                dead_interval=params.get("dead_interval") or params.get("dead_timer"),
                auth_key=params.get("auth_key") or params.get("password") or params.get("md5_key"),
                bgp_as_a=params.get("local_as") or params.get("as_a") or params.get("asn", "65001"),
                bgp_as_b=params.get("remote_as") or params.get("as_b") or params.get("asn", "65001"),
            )
        elif len(dev_names) > 2:
            # Ring or bus topology between devices in order
            for i in range(len(dev_names) - 1):
                u, v = dev_names[i], dev_names[i + 1]
                default_sub = f"10.0.{i}.0/30"
                self.graph.add_edge(
                    u,
                    v,
                    subnet=default_sub,
                    interface_a=f"GigabitEthernet0/{i+1}",
                    interface_b=f"GigabitEthernet0/{i+1}",
                    protocol=protocol,
                    ospf_area=params.get("area", "0"),
                    auth_key=params.get("auth_key") or params.get("password"),
                )

        return self.graph

    def extract_state_invariants(self, intent: StructuredIntent) -> List[StateInvariant]:
        """
        Extracts mandatory state invariants from the network graph that must be preserved
        across all connected router interfaces.
        """
        self.build_topology_from_intent(intent)
        invariants: List[StateInvariant] = []
        protocol = (intent.protocol or "").lower()
        params = intent.parameters or {}

        # 1. Connected Link Subnet Invariants
        for u, v, data in self.graph.edges(data=True):
            subnet = data.get("subnet")
            if subnet:
                invariants.append(
                    StateInvariant(
                        invariant_type="SHARED_LINK_SUBNET",
                        devices=[u, v],
                        parameters={
                            "subnet": subnet,
                            f"{u}_interface": data.get("interface_a"),
                            f"{v}_interface": data.get("interface_b"),
                        },
                        description=f"Link between {u} and {v} must be on shared subnet {subnet}.",
                    )
                )

            # 2. OSPF Invariants
            if "ospf" in protocol or "area" in params:
                area = data.get("ospf_area") or params.get("area", "0")
                invariants.append(
                    StateInvariant(
                        invariant_type="OSPF_AREA_ID",
                        devices=[u, v],
                        parameters={"area": str(area)},
                        description=f"OSPF Area ID must match across {u} and {v} link: Area {area}.",
                    )
                )
                if data.get("auth_key"):
                    invariants.append(
                        StateInvariant(
                            invariant_type="OSPF_AUTH_KEY",
                            devices=[u, v],
                            parameters={"auth_key": data.get("auth_key")},
                            description=f"Shared MD5/Authentication key across {u} and {v} must be '{data.get('auth_key')}'.",
                        )
                    )
                if data.get("hello_interval") or data.get("dead_interval"):
                    invariants.append(
                        StateInvariant(
                            invariant_type="OSPF_TIMERS",
                            devices=[u, v],
                            parameters={
                                "hello_interval": data.get("hello_interval"),
                                "dead_interval": data.get("dead_interval"),
                            },
                            description=f"OSPF Hello/Dead timers must match between {u} and {v}.",
                        )
                    )

            # 3. BGP Invariants
            if "bgp" in protocol or "as" in params or "asn" in params:
                as_u = data.get("bgp_as_a") or params.get("local_as") or params.get("asn", "65001")
                as_v = data.get("bgp_as_b") or params.get("remote_as") or params.get("asn", "65002")
                invariants.append(
                    StateInvariant(
                        invariant_type="BGP_SESSION",
                        devices=[u, v],
                        parameters={
                            f"{u}_local_as": as_u,
                            f"{u}_remote_as": as_v,
                            f"{v}_local_as": as_v,
                            f"{v}_remote_as": as_u,
                        },
                        description=f"BGP Session: {u} (AS {as_u}) peers with {v} (AS {as_v}).",
                    )
                )

            # 4. Invariants from Compiled Alignment Registry
            if self._alignment_registry and "protocols" in self._alignment_registry:
                reg_rules = self._alignment_registry["protocols"].get(protocol.upper(), [])
                for r in reg_rules:
                    p_id = r.get("parameter_identifier")
                    c_type = r.get("interoperability_constraint", {}).get("constraint_type")
                    if p_id in params and c_type == "EXACT_MATCH":
                        invariants.append(
                            StateInvariant(
                                invariant_type=f"REGISTRY_{p_id.upper()}",
                                devices=[u, v],
                                parameters={p_id: params[p_id]},
                                description=f"Alignment Rule [{r.get('rule_id')}]: {r.get('interoperability_constraint', {}).get('description')}",
                            )
                        )

        return invariants

    def build_constraint_injection_prompt(self, intent: StructuredIntent) -> str:
        """
        Builds the prompt injection section enforcing mandatory state invariants
        before querying the LLM for individual device configurations.
        """
        invariants = self.extract_state_invariants(intent)
        if not invariants:
            return ""

        prompt_lines = [
            "\n### STATE-INVARIANT GRAPH CONTROLLER: MANDATORY INVARIANTS ###",
            "The following state invariants are mathematically fixed across the network graph.",
            "You MUST conform to these exact topological parameters to prevent adjacency and session failure:\n",
        ]

        for inv in invariants:
            prompt_lines.append(f"- **[{inv.invariant_type}]** {inv.description}")
            for k, val in inv.parameters.items():
                if val is not None:
                    prompt_lines.append(f"    * {k}: {val}")

        prompt_lines.append(
            "\nCRITICAL: Any divergence in Area IDs, subnet IPs, AS numbers, or timers between connecting interfaces "
            "will be intercepted and rejected by the State-Invariant Graph Controller.\n"
        )
        return "\n".join(prompt_lines)

    def intercept_and_validate(
        self,
        intent: StructuredIntent,
        synthesized_configs: Dict[str, str],
    ) -> ConflictResolutionResult:
        """
        Interactive Interception: Parses generated configuration blocks across adjacent nodes.
        If connecting interface parameters diverge, intercepts output, flags the exact conflict,
        and generates an automated self-correction prompt.
        """
        conflicts: List[Dict[str, Any]] = []
        if len(synthesized_configs) < 2:
            return ConflictResolutionResult(has_conflicts=False, conflicts=[])

        self.build_topology_from_intent(intent)

        # Parse extracted config parameters per device
        extracted_state: Dict[str, Dict[str, Any]] = {}
        for dev_name, cfg in synthesized_configs.items():
            extracted_state[dev_name] = self._parse_device_state(cfg)

        # Check edge invariants across connected devices
        for u, v, edge_data in self.graph.edges(data=True):
            if u not in extracted_state or v not in extracted_state:
                continue

            state_u = extracted_state[u]
            state_v = extracted_state[v]

            # 1. OSPF Area check
            if state_u.get("ospf_areas") and state_v.get("ospf_areas"):
                areas_u = state_u["ospf_areas"]
                areas_v = state_v["ospf_areas"]
                common_areas = areas_u.intersection(areas_v)
                if not common_areas:
                    conflicts.append({
                        "type": "OSPF_AREA_MISMATCH",
                        "devices": [u, v],
                        "details": f"{u} configures OSPF area(s) {list(areas_u)} while adjacent {v} configures {list(areas_v)}.",
                        "fix": f"Synchronize OSPF Area ID on both routers to Area {edge_data.get('ospf_area', '0')}.",
                    })

            # 2. OSPF Hello/Dead Timers check
            if state_u.get("ospf_hello") and state_v.get("ospf_hello"):
                if state_u["ospf_hello"] != state_v["ospf_hello"]:
                    conflicts.append({
                        "type": "OSPF_HELLO_MISMATCH",
                        "devices": [u, v],
                        "details": f"{u} hello interval ({state_u['ospf_hello']}) does not match {v} ({state_v['ospf_hello']}).",
                        "fix": f"Set hello interval to {state_u['ospf_hello']} on both devices.",
                    })

            # 3. OSPF MD5 Authentication Key check
            if state_u.get("ospf_keys") and state_v.get("ospf_keys"):
                common_keys = state_u["ospf_keys"].intersection(state_v["ospf_keys"])
                if not common_keys:
                    conflicts.append({
                        "type": "OSPF_AUTH_KEY_MISMATCH",
                        "devices": [u, v],
                        "details": f"OSPF authentication keys differ between {u} and {v}.",
                        "fix": f"Configure identical MD5 message-digest key across connecting interfaces on {u} and {v}.",
                    })

            # 4. Interface Subnet Check
            ips_u = state_u.get("interface_ips", [])
            ips_v = state_v.get("interface_ips", [])
            connected_subnet_found = False
            if ips_u and ips_v:
                for ip_u_str in ips_u:
                    try:
                        net_u = ipaddress.ip_interface(ip_u_str).network
                        for ip_v_str in ips_v:
                            net_v = ipaddress.ip_interface(ip_v_str).network
                            if net_u == net_v:
                                connected_subnet_found = True
                                break
                    except Exception:
                        continue
                if not connected_subnet_found and edge_data.get("subnet"):
                    conflicts.append({
                        "type": "SUBNET_MISMATCH",
                        "devices": [u, v],
                        "details": f"Interfaces on connecting link between {u} and {v} are not in the same IP subnet (Expected: {edge_data.get('subnet')}).",
                        "fix": f"Assign adjacent IP addresses from {edge_data.get('subnet')} to {u} and {v}.",
                    })

            # 5. BGP remote-as and neighbor alignment
            bgp_u = state_u.get("bgp", {})
            bgp_v = state_v.get("bgp", {})
            if bgp_u and bgp_v:
                # If u has neighbor with v's AS, check match
                local_as_u = bgp_u.get("local_as")
                local_as_v = bgp_v.get("local_as")
                peers_u = bgp_u.get("neighbors", {})  # ip -> remote_as
                peers_v = bgp_v.get("neighbors", {})

                if local_as_v and peers_u:
                    # check if any neighbor points to local_as_v
                    matched_asn = any(rem_as == local_as_v for rem_as in peers_u.values())
                    if not matched_asn and peers_u.values():
                        conflicts.append({
                            "type": "BGP_REMOTE_AS_MISMATCH",
                            "devices": [u, v],
                            "details": f"{u} expected {v} remote-as {list(peers_u.values())}, but {v} configured local ASN {local_as_v}.",
                            "fix": f"Align BGP remote-as on {u} to match {v}'s AS ({local_as_v}).",
                        })

        if not conflicts:
            return ConflictResolutionResult(has_conflicts=False, conflicts=[])

        # Generate self-correction prompt
        remediation_lines = [
            "STATE-INVARIANT GRAPH CONTROLLER INTERCEPTION:",
            "The synthesized configuration contains parameter discrepancies between adjacent nodes that violate topological invariants:\n"
        ]
        for c in conflicts:
            remediation_lines.append(f"• [{c['type']}] ({' <-> '.join(c['devices'])}): {c['details']}")
            remediation_lines.append(f"  REQUIRED FIX: {c['fix']}")
        remediation_lines.append(
            "\nPlease revise the configuration commands for the affected device(s) to resolve these topological invariants exactly."
        )

        return ConflictResolutionResult(
            has_conflicts=True,
            conflicts=conflicts,
            remediation_prompt="\n".join(remediation_lines),
        )

    def _parse_device_state(self, config_text: str) -> Dict[str, Any]:
        """Parses basic state parameters from Cisco and Juniper/VyOS CLI text."""
        state: Dict[str, Any] = {
            "ospf_areas": set(),
            "ospf_hello": None,
            "ospf_dead": None,
            "ospf_keys": set(),
            "interface_ips": [],
            "bgp": {"local_as": None, "neighbors": {}},
        }

        # OSPF Area
        # Cisco: network 10.0.0.0 0.0.0.3 area 0 OR ip ospf 1 area 0
        for match in re.finditer(r"(?:network\s+\S+\s+\S+\s+area|ip\s+ospf(?:\s+\d+)?\s+area|set\s+protocols\s+ospf\s+area)\s+(\S+)", config_text, re.IGNORECASE):
            area_val = match.group(1).strip()
            state["ospf_areas"].add(area_val)

        # OSPF Timers
        # ip ospf hello-interval 5 / set protocols ospf area 0 hello-interval 5
        hello_m = re.search(r"hello-interval\s+(\d+)", config_text, re.IGNORECASE)
        if hello_m:
            state["ospf_hello"] = int(hello_m.group(1))

        dead_m = re.search(r"dead-interval\s+(\d+)", config_text, re.IGNORECASE)
        if dead_m:
            state["ospf_dead"] = int(dead_m.group(1))

        # OSPF Key
        # ip ospf message-digest-key 1 md5 CISCOKEY
        for key_m in re.finditer(r"message-digest-key\s+\d+\s+md5\s+(\S+)", config_text, re.IGNORECASE):
            state["ospf_keys"].add(key_m.group(1))

        # Interface IPs
        # Cisco: ip address 10.0.0.1 255.255.255.252
        for ip_m in re.finditer(r"ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", config_text, re.IGNORECASE):
            ip_val = ip_m.group(1)
            mask_val = ip_m.group(2)
            try:
                state["interface_ips"].append(f"{ip_val}/{mask_val}")
            except Exception:
                pass

        # Juniper/VyOS: set interfaces ethernet eth0 address 10.0.0.1/30
        for ip_m in re.finditer(r"address\s+(\d+\.\d+\.\d+\.\d+/\d+)", config_text, re.IGNORECASE):
            state["interface_ips"].append(ip_m.group(1))

        # BGP
        # router bgp 65001 / set protocols bgp 65001
        bgp_as_m = re.search(r"(?:router\s+bgp|protocols\s+bgp(?:\s+local-as)?)\s+(\d+)", config_text, re.IGNORECASE)
        if bgp_as_m:
            state["bgp"]["local_as"] = bgp_as_m.group(1)

        # Cisco neighbor: neighbor 10.0.0.2 remote-as 65002
        for n_m in re.finditer(r"neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+remote-as\s+(\d+)", config_text, re.IGNORECASE):
            state["bgp"]["neighbors"][n_m.group(1)] = n_m.group(2)

        # VyOS neighbor: set protocols bgp ... neighbor 10.0.0.2 remote-as 65002
        for n_m in re.finditer(r"neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+remote-as\s+(\d+)", config_text, re.IGNORECASE):
            state["bgp"]["neighbors"][n_m.group(1)] = n_m.group(2)

        return state
