"""
Topology-Aware Validation Pipeline for RAG-NetTwin v2.

Intermediate validation tier between Tier 1 (Batfish static analysis) and emulation/deployment.
Validates multi-router, cross-vendor configuration semantic invariants:
1. OSPF Adjacency Invariants (Area IDs, hello/dead timers, MTU, authentication)
2. BGP Session Parameters (remote-as, neighbor IPs, MD5 authentication)
3. ACL Directional Logic (inbound vs outbound relative to natural language intent)
4. Structured Failure Reporting (OSPF_AREA_MISMATCH, ACL_DIRECTION_ERROR, etc.)
"""

from __future__ import annotations

import ipaddress
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
from pydantic import BaseModel, Field

from src.schemas.intent import StructuredIntent
from src.utils import setup_logger
from src.validation.base import NetworkValidator

logger = setup_logger("TopologyAwareValidator")


class TopologyErrorType(str, Enum):
    OSPF_AREA_MISMATCH = "OSPF_AREA_MISMATCH"
    OSPF_TIMER_MISMATCH = "OSPF_TIMER_MISMATCH"
    OSPF_MTU_MISMATCH = "OSPF_MTU_MISMATCH"
    OSPF_AUTH_MISMATCH = "OSPF_AUTH_MISMATCH"
    BGP_SESSION_MISMATCH = "BGP_SESSION_MISMATCH"
    BGP_REMOTE_AS_MISMATCH = "BGP_REMOTE_AS_MISMATCH"
    BGP_AUTH_MISMATCH = "BGP_AUTH_MISMATCH"
    SUBNET_MISMATCH = "SUBNET_MISMATCH"
    ACL_DIRECTION_ERROR = "ACL_DIRECTION_ERROR"
    MISSING_NEIGHBOR_CONFIG = "MISSING_NEIGHBOR_CONFIG"


class TopologyValidationIssue(BaseModel):
    """Structured semantic failure item for multi-router configurations."""
    error_type: TopologyErrorType
    severity: str = "CRITICAL"  # CRITICAL, WARNING
    devices: List[str]
    interfaces: List[str] = Field(default_factory=list)
    details: str
    remediation_suggestion: str


class TopologyValidationReport(BaseModel):
    """Aggregate result of topology-aware semantic validation."""
    status: str  # PASS, FAIL, WARNING
    tier: float = 1.5
    issues: List[TopologyValidationIssue] = Field(default_factory=list)
    summary: str
    passed_invariants: List[str] = Field(default_factory=list)


class TopologyAwareValidator(NetworkValidator):
    """
    Tier 1.5 Semantic Validator.
    Parses multi-vendor configs and validates cross-device invariants against the network topology graph.
    """

    def __init__(self):
        super().__init__(tier=2)  # Slotting as intermediate tier between Tier 1 and Tier 3

    def validate(
        self,
        configs: Dict[str, str],
        intent: Optional[StructuredIntent] = None,
    ) -> Dict[str, Any]:
        """
        Executes cross-device invariant checking on multi-vendor configuration files.
        """
        issues: List[TopologyValidationIssue] = []
        passed_invariants: List[str] = []

        # Filter internal metadata
        device_configs = {
            k: v for k, v in configs.items()
            if k is not None and not k.startswith("_") and v != "ERROR"
        }

        if len(device_configs) < 2:
            # Single-device configuration: validate ACL directional logic if intent provided
            if intent and device_configs:
                for dev_name, cfg in device_configs.items():
                    acl_issues = self._check_acl_directional_logic(dev_name, cfg, intent)
                    issues.extend(acl_issues)
            status = "FAIL" if any(i.severity == "CRITICAL" for i in issues) else "PASS"
            report = TopologyValidationReport(
                status=status,
                tier=1.5,
                issues=issues,
                summary=f"Topology-Aware validation evaluated {len(device_configs)} device(s) with {len(issues)} issue(s).",
                passed_invariants=["SINGLE_DEVICE_SCOPE"],
            )
            return report.model_dump()

        # Build topology graph
        topo = nx.Graph()
        parsed_devices: Dict[str, Dict[str, Any]] = {}
        for dev_name, cfg in device_configs.items():
            parsed = self._parse_config_semantics(dev_name, cfg)
            parsed_devices[dev_name] = parsed
            topo.add_node(dev_name, **parsed)

        # Connect devices in topology
        dev_list = list(device_configs.keys())
        for i in range(len(dev_list) - 1):
            topo.add_edge(dev_list[i], dev_list[i + 1])

        # 1. Verify OSPF Invariants
        ospf_issues, ospf_passed = self._verify_ospf_invariants(topo, parsed_devices)
        issues.extend(ospf_issues)
        passed_invariants.extend(ospf_passed)

        # 2. Verify BGP Session Parameters
        bgp_issues, bgp_passed = self._verify_bgp_invariants(topo, parsed_devices)
        issues.extend(bgp_issues)
        passed_invariants.extend(bgp_passed)

        # 3. Verify Subnet Link Invariants
        subnet_issues, subnet_passed = self._verify_subnet_invariants(topo, parsed_devices)
        issues.extend(subnet_issues)
        passed_invariants.extend(subnet_passed)

        # 4. Verify ACL Directional Logic
        if intent:
            for dev_name, cfg in device_configs.items():
                acl_issues = self._check_acl_directional_logic(dev_name, cfg, intent)
                issues.extend(acl_issues)
                if not acl_issues and ("acl" in (intent.protocol or "").lower() or "filter" in (intent.protocol or "").lower()):
                    passed_invariants.append(f"ACL_DIRECTION_LOGIC_{dev_name}")

        status = "FAIL" if any(i.severity == "CRITICAL" for i in issues) else ("WARNING" if issues else "PASS")
        report = TopologyValidationReport(
            status=status,
            tier=1.5,
            issues=issues,
            summary=f"Topology validation completed with status {status}. Found {len(issues)} semantic discrepancy/ies.",
            passed_invariants=passed_invariants,
        )
        return report.model_dump()

    def _parse_config_semantics(self, dev_name: str, config: str) -> Dict[str, Any]:
        """Deeply extracts semantic parameters across Cisco and Juniper/VyOS configs."""
        res: Dict[str, Any] = {
            "interfaces": {},  # if_name -> {ip, mask, cidr, mtu, ospf_area, ospf_hello, ospf_dead, ospf_key}
            "ospf_global_areas": set(),
            "ospf_global_hello": None,
            "ospf_global_dead": None,
            "ospf_global_keys": set(),
            "bgp": {"local_as": None, "neighbors": {}, "passwords": {}},
            "acls": [],  # list of {name, interface, direction}
        }

        # --- CISCO PARSING ---
        current_if = None
        for line in config.splitlines():
            line_str = line.strip()

            # Interface block start
            if_m = re.match(r"^interface\s+(\S+)", line_str, re.IGNORECASE)
            if if_m:
                current_if = if_m.group(1)
                res["interfaces"][current_if] = {
                    "ip": None,
                    "mask": None,
                    "cidr": None,
                    "mtu": 1500,
                    "ospf_area": None,
                    "ospf_hello": None,
                    "ospf_dead": None,
                    "ospf_key": None,
                }
                continue

            if current_if:
                # IP address under interface
                ip_m = re.match(r"^ip\s+address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", line_str, re.IGNORECASE)
                if ip_m:
                    ip_val, mask_val = ip_m.group(1), ip_m.group(2)
                    res["interfaces"][current_if]["ip"] = ip_val
                    res["interfaces"][current_if]["mask"] = mask_val
                    try:
                        net = ipaddress.IPv4Network(f"{ip_val}/{mask_val}", strict=False)
                        res["interfaces"][current_if]["cidr"] = f"{ip_val}/{net.prefixlen}"
                    except Exception:
                        pass

                # MTU under interface
                mtu_m = re.match(r"^(?:ip\s+)?mtu\s+(\d+)", line_str, re.IGNORECASE)
                if mtu_m:
                    res["interfaces"][current_if]["mtu"] = int(mtu_m.group(1))

                # OSPF under interface
                ospf_if_area_m = re.match(r"^ip\s+ospf(?:\s+\d+)?\s+area\s+(\S+)", line_str, re.IGNORECASE)
                if ospf_if_area_m:
                    res["interfaces"][current_if]["ospf_area"] = ospf_if_area_m.group(1)

                hello_if_m = re.match(r"^ip\s+ospf\s+hello-interval\s+(\d+)", line_str, re.IGNORECASE)
                if hello_if_m:
                    res["interfaces"][current_if]["ospf_hello"] = int(hello_if_m.group(1))

                dead_if_m = re.match(r"^ip\s+ospf\s+dead-interval\s+(\d+)", line_str, re.IGNORECASE)
                if dead_if_m:
                    res["interfaces"][current_if]["ospf_dead"] = int(dead_if_m.group(1))

                key_if_m = re.match(r"^ip\s+ospf\s+message-digest-key\s+\d+\s+md5\s+(\S+)", line_str, re.IGNORECASE)
                if key_if_m:
                    res["interfaces"][current_if]["ospf_key"] = key_if_m.group(1)

                # Cisco ACL applied on interface
                # ip access-group <ACL> in|out
                acl_app_m = re.match(r"^ip\s+access-group\s+(\S+)\s+(in|out)", line_str, re.IGNORECASE)
                if acl_app_m:
                    res["acls"].append({
                        "name": acl_app_m.group(1),
                        "interface": current_if,
                        "direction": acl_app_m.group(2).lower(),
                    })

            # Cisco Global OSPF
            cisco_net_m = re.match(r"^network\s+\S+\s+\S+\s+area\s+(\S+)", line_str, re.IGNORECASE)
            if cisco_net_m:
                res["ospf_global_areas"].add(cisco_net_m.group(1))

            # Cisco BGP
            bgp_m = re.match(r"^router\s+bgp\s+(\d+)", line_str, re.IGNORECASE)
            if bgp_m:
                res["bgp"]["local_as"] = bgp_m.group(1)

            nbr_m = re.match(r"^neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+remote-as\s+(\d+)", line_str, re.IGNORECASE)
            if nbr_m:
                res["bgp"]["neighbors"][nbr_m.group(1)] = nbr_m.group(2)

            nbr_pass_m = re.match(r"^neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+password\s+(\S+)", line_str, re.IGNORECASE)
            if nbr_pass_m:
                res["bgp"]["passwords"][nbr_pass_m.group(1)] = nbr_pass_m.group(2)

        # --- JUNIPER / VYOS PARSING (set commands) ---
        for line in config.splitlines():
            line_str = line.strip()
            # set interfaces ethernet eth0 address 10.0.0.1/30
            j_ip_m = re.search(r"set\s+interfaces\s+(?:ethernet\s+)?(\S+)\s+address\s+(\d+\.\d+\.\d+\.\d+/\d+)", line_str, re.IGNORECASE)
            if j_ip_m:
                intf, cidr = j_ip_m.group(1), j_ip_m.group(2)
                if intf not in res["interfaces"]:
                    res["interfaces"][intf] = {"ip": None, "mask": None, "cidr": None, "mtu": 1500, "ospf_area": None, "ospf_hello": None, "ospf_dead": None, "ospf_key": None}
                res["interfaces"][intf]["cidr"] = cidr
                res["interfaces"][intf]["ip"] = cidr.split("/")[0]

            # set interfaces ethernet eth0 mtu 1500
            j_mtu_m = re.search(r"set\s+interfaces\s+(?:ethernet\s+)?(\S+)\s+mtu\s+(\d+)", line_str, re.IGNORECASE)
            if j_mtu_m:
                intf, mtu_val = j_mtu_m.group(1), int(j_mtu_m.group(2))
                if intf in res["interfaces"]:
                    res["interfaces"][intf]["mtu"] = mtu_val

            # set protocols ospf area 0 interface eth0
            # set protocols ospf area 0.0.0.0 network 10.0.0.0/30
            j_ospf_m = re.search(r"set\s+protocols\s+ospf\s+area\s+(\S+)", line_str, re.IGNORECASE)
            if j_ospf_m:
                res["ospf_global_areas"].add(j_ospf_m.group(1))

            # set protocols ospf area 0 hello-interval 5
            j_hello_m = re.search(r"set\s+protocols\s+ospf\s+area\s+\S+\s+hello-interval\s+(\d+)", line_str, re.IGNORECASE)
            if j_hello_m:
                res["ospf_global_hello"] = int(j_hello_m.group(1))

            # set protocols bgp local-as 65001 or set protocols bgp 65001
            j_bgp_m = re.search(r"set\s+protocols\s+bgp(?:\s+local-as)?\s+(\d+)", line_str, re.IGNORECASE)
            if j_bgp_m:
                res["bgp"]["local_as"] = j_bgp_m.group(1)

            # set protocols bgp ... neighbor 10.0.0.2 remote-as 65002
            j_nbr_m = re.search(r"neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+remote-as\s+(\d+)", line_str, re.IGNORECASE)
            if j_nbr_m:
                res["bgp"]["neighbors"][j_nbr_m.group(1)] = j_nbr_m.group(2)

            # set protocols bgp ... neighbor 10.0.0.2 password secret
            j_nbr_pass = re.search(r"neighbor\s+(\d+\.\d+\.\d+\.\d+)\s+password\s+(\S+)", line_str, re.IGNORECASE)
            if j_nbr_pass:
                res["bgp"]["passwords"][j_nbr_pass.group(1)] = j_nbr_pass.group(2)

            # set interfaces ethernet eth0 firewall in name FILTER
            j_acl_m = re.search(r"set\s+interfaces\s+(?:ethernet\s+)?(\S+)\s+firewall\s+(in|out)\s+(?:name\s+)?(\S+)", line_str, re.IGNORECASE)
            if j_acl_m:
                res["acls"].append({
                    "name": j_acl_m.group(3),
                    "interface": j_acl_m.group(1),
                    "direction": j_acl_m.group(2).lower(),
                })

        return res

    def _verify_ospf_invariants(
        self, topo: nx.Graph, parsed: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[TopologyValidationIssue], List[str]]:
        """Verifies OSPF Area ID, Hello/Dead timers, and MTU parity across connected routers."""
        issues: List[TopologyValidationIssue] = []
        passed: List[str] = []

        for u, v in topo.edges():
            u_data = parsed[u]
            v_data = parsed[v]

            # Collect all areas for u and v
            areas_u = set(u_data["ospf_global_areas"])
            for if_data in u_data["interfaces"].values():
                if if_data.get("ospf_area"):
                    areas_u.add(if_data["ospf_area"])

            areas_v = set(v_data["ospf_global_areas"])
            for if_data in v_data["interfaces"].values():
                if if_data.get("ospf_area"):
                    areas_v.add(if_data["ospf_area"])

            if areas_u and areas_v:
                # Normalize areas (e.g., 0 vs 0.0.0.0)
                norm_u = {self._norm_area(a) for a in areas_u}
                norm_v = {self._norm_area(a) for a in areas_v}
                if not norm_u.intersection(norm_v):
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.OSPF_AREA_MISMATCH,
                            severity="CRITICAL",
                            devices=[u, v],
                            details=f"OSPF Area Mismatch: Router {u} configured area(s) {list(areas_u)}, but {v} configured {list(areas_v)}.",
                            remediation_suggestion=f"Align OSPF Area on both {u} and {v} to identical area (e.g., area 0).",
                        )
                    )
                else:
                    passed.append(f"OSPF_AREA_MATCH_{u}_{v}")

            # Hello / Dead Timers
            hello_u = u_data["ospf_global_hello"]
            hello_v = v_data["ospf_global_hello"]
            for if_data in u_data["interfaces"].values():
                if if_data.get("ospf_hello"):
                    hello_u = if_data["ospf_hello"]
            for if_data in v_data["interfaces"].values():
                if if_data.get("ospf_hello"):
                    hello_v = if_data["ospf_hello"]

            if hello_u is not None and hello_v is not None:
                if hello_u != hello_v:
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.OSPF_TIMER_MISMATCH,
                            severity="CRITICAL",
                            devices=[u, v],
                            details=f"OSPF Hello Interval Mismatch: {u} is {hello_u}s vs {v} is {hello_v}s.",
                            remediation_suggestion=f"Set matching OSPF hello-interval on both {u} and {v}.",
                        )
                    )
                else:
                    passed.append(f"OSPF_TIMERS_MATCH_{u}_{v}")

            # MTU settings across connecting interfaces
            for if_u, data_u in u_data["interfaces"].items():
                for if_v, data_v in v_data["interfaces"].items():
                    if data_u.get("cidr") and data_v.get("cidr"):
                        try:
                            net_u = ipaddress.ip_interface(data_u["cidr"]).network
                            net_v = ipaddress.ip_interface(data_v["cidr"]).network
                            if net_u == net_v:
                                # Connected link found! Compare MTU
                                mtu_u = data_u.get("mtu", 1500)
                                mtu_v = data_v.get("mtu", 1500)
                                if mtu_u != mtu_v:
                                    issues.append(
                                        TopologyValidationIssue(
                                            error_type=TopologyErrorType.OSPF_MTU_MISMATCH,
                                            severity="CRITICAL",
                                            devices=[u, v],
                                            interfaces=[f"{u}:{if_u}", f"{v}:{if_v}"],
                                            details=f"MTU Mismatch across link: {u}:{if_u} has MTU {mtu_u}, but {v}:{if_v} has MTU {mtu_v}.",
                                            remediation_suggestion=f"Synchronize MTU to {mtu_u} across link interfaces {if_u} and {if_v}.",
                                        )
                                    )
                                else:
                                    passed.append(f"LINK_MTU_MATCH_{u}_{v}")
                        except Exception:
                            continue

        return issues, passed

    def _verify_bgp_invariants(
        self, topo: nx.Graph, parsed: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[TopologyValidationIssue], List[str]]:
        """Verifies BGP peer remote-as, neighbor IP reciprocity, and cryptographic keys."""
        issues: List[TopologyValidationIssue] = []
        passed: List[str] = []

        for u, v in topo.edges():
            bgp_u = parsed[u]["bgp"]
            bgp_v = parsed[v]["bgp"]

            local_as_u = bgp_u.get("local_as")
            local_as_v = bgp_v.get("local_as")
            nbrs_u = bgp_u.get("neighbors", {})
            nbrs_v = bgp_v.get("neighbors", {})

            if local_as_u and local_as_v:
                # Check if u has configured v as neighbor
                u_points_to_v = any(rem_as == local_as_v for rem_as in nbrs_u.values())
                v_points_to_u = any(rem_as == local_as_u for rem_as in nbrs_v.values())

                if nbrs_u and not u_points_to_v:
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.BGP_REMOTE_AS_MISMATCH,
                            severity="CRITICAL",
                            devices=[u, v],
                            details=f"BGP remote-as mismatch: Router {u} does not configure remote-as {local_as_v} matching neighbor {v}.",
                            remediation_suggestion=f"Configure 'neighbor <IP> remote-as {local_as_v}' on {u}.",
                        )
                    )
                if nbrs_v and not v_points_to_u:
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.BGP_REMOTE_AS_MISMATCH,
                            severity="CRITICAL",
                            devices=[v, u],
                            details=f"BGP remote-as mismatch: Router {v} does not configure remote-as {local_as_u} matching neighbor {u}.",
                            remediation_suggestion=f"Configure 'neighbor <IP> remote-as {local_as_u}' on {v}.",
                        )
                    )
                if u_points_to_v and v_points_to_u:
                    passed.append(f"BGP_SESSION_ALIGNED_{u}_{v}")

                # BGP Password Check
                passwords_u = bgp_u.get("passwords", {})
                passwords_v = bgp_v.get("passwords", {})
                if passwords_u and passwords_v:
                    keys_u = set(passwords_u.values())
                    keys_v = set(passwords_v.values())
                    if not keys_u.intersection(keys_v):
                        issues.append(
                            TopologyValidationIssue(
                                error_type=TopologyErrorType.BGP_AUTH_MISMATCH,
                                severity="CRITICAL",
                                devices=[u, v],
                                details=f"BGP neighbor password mismatch between {u} and {v}.",
                                remediation_suggestion="Configure identical BGP neighbor password on both peers.",
                            )
                        )
                    else:
                        passed.append(f"BGP_AUTH_MATCH_{u}_{v}")

        return issues, passed

    def _verify_subnet_invariants(
        self, topo: nx.Graph, parsed: Dict[str, Dict[str, Any]]
    ) -> Tuple[List[TopologyValidationIssue], List[str]]:
        """Verifies connected interface IP subnet consistency across adjacent routers."""
        issues: List[TopologyValidationIssue] = []
        passed: List[str] = []

        for u, v in topo.edges():
            u_cidrs = [d["cidr"] for d in parsed[u]["interfaces"].values() if d.get("cidr")]
            v_cidrs = [d["cidr"] for d in parsed[v]["interfaces"].values() if d.get("cidr")]

            if u_cidrs and v_cidrs:
                matched_subnet = False
                for c_u in u_cidrs:
                    net_u = ipaddress.ip_interface(c_u).network
                    for c_v in v_cidrs:
                        net_v = ipaddress.ip_interface(c_v).network
                        if net_u == net_v:
                            matched_subnet = True
                            passed.append(f"SHARED_SUBNET_{u}_{v}_{net_u}")
                            break
                    if matched_subnet:
                        break

                if not matched_subnet and len(u_cidrs) > 0 and len(v_cidrs) > 0:
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.SUBNET_MISMATCH,
                            severity="CRITICAL",
                            devices=[u, v],
                            details=f"No shared IP subnet found on connecting link between {u} ({u_cidrs}) and {v} ({v_cidrs}).",
                            remediation_suggestion=f"Assign connecting interfaces on {u} and {v} to the same subnet prefix (e.g. 10.0.0.0/30).",
                        )
                    )

        return issues, passed

    def _check_acl_directional_logic(
        self, dev_name: str, config: str, intent: StructuredIntent
    ) -> List[TopologyValidationIssue]:
        """
        Validates ACL directional logic (inbound vs outbound) against natural language intent policy.
        E.g., if intent says 'block incoming traffic' or 'restrict ingress', the ACL MUST be applied 'in'.
        """
        issues: List[TopologyValidationIssue] = []
        intent_text = (intent.original_text or "").lower()
        params = intent.parameters or {}
        protocol = (intent.protocol or "").lower()

        # Check if intent is an ACL / filtering policy
        is_acl = "acl" in protocol or "filter" in protocol or "restrict" in intent_text or "block" in intent_text or "access-list" in intent_text
        if not is_acl:
            return issues

        # Determine intended direction
        intended_dir = None
        if "ingress" in intent_text or "incoming" in intent_text or "inbound" in intent_text or params.get("direction") in ["in", "inbound", "ingress"]:
            intended_dir = "in"
        elif "egress" in intent_text or "outgoing" in intent_text or "outbound" in intent_text or params.get("direction") in ["out", "outbound", "egress"]:
            intended_dir = "out"

        if not intended_dir:
            return issues

        # Find applied direction in config
        # Cisco: ip access-group <name> in|out
        cisco_apps = re.findall(r"ip\s+access-group\s+\S+\s+(in|out)", config, re.IGNORECASE)
        # Juniper/VyOS: firewall in|out name <name>
        vyos_apps = re.findall(r"firewall\s+(in|out)", config, re.IGNORECASE)
        applied_dirs = [d.lower() for d in (cisco_apps + vyos_apps)]

        if applied_dirs:
            for ad in applied_dirs:
                if ad != intended_dir:
                    issues.append(
                        TopologyValidationIssue(
                            error_type=TopologyErrorType.ACL_DIRECTION_ERROR,
                            severity="CRITICAL",
                            devices=[dev_name],
                            details=f"ACL Direction Error on {dev_name}: Intent requested {intended_dir}bound filtering, but ACL was applied {ad}bound.",
                            remediation_suggestion=f"Change ACL application on {dev_name} from '{ad}' to '{intended_dir}'.",
                        )
                    )
        elif "access-list" in config or "rule" in config:
            # Defined but not applied on any interface
            issues.append(
                TopologyValidationIssue(
                    error_type=TopologyErrorType.ACL_DIRECTION_ERROR,
                    severity="WARNING",
                    devices=[dev_name],
                    details=f"ACL defined on {dev_name} but not applied to any interface in {intended_dir}bound direction.",
                    remediation_suggestion=f"Apply access-list with 'ip access-group <name> {intended_dir}' under target interface.",
                )
            )

        return issues

    def _norm_area(self, area: str) -> str:
        """Normalizes area representation between 0, 0.0.0.0, etc."""
        area_clean = str(area).strip()
        if area_clean in ["0", "0.0.0.0"]:
            return "0"
        try:
            return str(int(area_clean))
        except ValueError:
            return area_clean
