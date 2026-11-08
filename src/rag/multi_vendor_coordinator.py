import ipaddress
import json
import re
from typing import Any, cast

from pydantic import BaseModel, Field

from src.utils import setup_logger

logger = setup_logger("MultiVendorCoordinator")


class InteroperabilityConstraint(BaseModel):
    """
    Represents a shared parameter that must match across different vendors.
    """

    parameter_name: str
    value: Any
    protocol: str
    importance: str = "CRITICAL"


class NetworkMasterPlan(BaseModel):
    """
    Proposed global parameters for a multi-device intent.
    """

    proposed_parameters: dict[str, dict[str, Any]] = Field(
        description="Map of device name -> parameter dictionary"
    )
    deployment_sequence: list[str] = Field(
        description="Logical order of operations for the entire topology (e.g. 1. Interfaces, 2. Routing)"
    )
    rationale: str = Field(description="Explanation of the planning decisions")


class MultiVendorCoordinator:
    """
    Coordinates configuration consistency across heterogeneous vendors (Recommendation 2).
    Addresses RQ3: Semantic correctness in multi-vendor environments.
    """

    def __init__(self):
        # Maps intent parameters to their interoperability equivalents
        # Example: Cisco 'area' == Juniper 'area'
        self.interop_map = {
            "ospf": [
                "area",
                "process_id",
                "hello_interval",
                "dead_interval",
                "wildcard_mask",
            ],
            "bgp": ["local_as", "remote_as", "peer_group", "hold_time"],
            "vlan": ["vlan_id", "vlan_name"],
            "interface": ["mtu", "speed", "duplex", "subnet_mask"],
        }

    def extract_shared_constraints(
        self, intent: Any
    ) -> list[InteroperabilityConstraint]:
        """
        Identifies parameters in the intent that must be consistent across all devices.
        """
        constraints = []
        protocol = (intent.protocol or "").lower()
        params = intent.parameters or {}

        if protocol in self.interop_map:
            for param_key in self.interop_map[protocol]:
                if param_key in params:
                    constraints.append(
                        InteroperabilityConstraint(
                            parameter_name=param_key,
                            value=params[param_key],
                            protocol=protocol,
                        )
                    )

        # Generic parameter extraction for cross-vendor logic
        # e.g., if 'ip' is mentioned, we might need subnet consistency (future enhancement)

        return constraints

    def build_coordination_prompt(
        self,
        constraints: list[InteroperabilityConstraint],
        master_plan: NetworkMasterPlan | None = None,
    ) -> str:
        """
        Generates a prompt snippet to force the LLM to respect shared constraints
        and follow the global network plan.
        """
        prompt = ""

        if constraints:
            prompt += "\n### SHARED PARAMETER CONSTRAINTS ###\n"
            prompt += "To ensure the network functions correctly, you MUST use these exact values:\n"
            for c in constraints:
                prompt += f"- {c.protocol.upper()} {c.parameter_name}: {c.value}\n"

        if master_plan:
            prompt += "\n### GLOBAL NETWORK MASTER PLAN ###\n"
            prompt += (
                "The following parameters have been pre-calculated for this topology. "
            )
            prompt += "You MUST follow these assignments to ensure peer adjacencies form correctly:\n"
            prompt += json.dumps(master_plan.proposed_parameters, indent=2) + "\n"

            if master_plan.deployment_sequence:
                prompt += "\n### DEPLOYMENT SEQUENCE ###\n"
                prompt += "Follow this logical order of operations in your generated commands:\n"
                for i, step in enumerate(master_plan.deployment_sequence):
                    prompt += f"{i + 1}. {step}\n"

            prompt += f"\nPLANNING RATIONALE: {master_plan.rationale}\n"

        if prompt:
            prompt += "\nFailure to follow these constraints will result in a Tier 3 Functional Error.\n"

        return prompt

    def generate_interop_plan(self, intent: Any) -> NetworkMasterPlan:
        """
        Deterministically builds a consistent network plan for all devices from intent parameters
        and topology awareness, avoiding redundant LLM roundtrips and token consumption.
        """
        logger.info("Generating deterministic interoperability plan...")

        proposed_params: dict[str, dict[str, Any]] = {}
        devices = getattr(intent, "devices", [])
        params = getattr(intent, "parameters", {}) or {}

        # Default sequence
        sequence = [
            "Configure physical/logical interfaces",
            "Assign IP addressing and subnets",
            "Enable routing protocol peering",
        ]

        # Extract base parameters
        for idx, dev in enumerate(devices):
            dev_name = getattr(dev, "name", f"Device{idx+1}")
            dev_dict: dict[str, Any] = {}
            for k, v in params.items():
                dev_dict[k] = v
            proposed_params[dev_name] = dev_dict

        # Deterministic Peer IP Disambiguation for Point-to-Point Links/Tunnels
        if len(devices) > 1:
            subnet_val = None
            subnet_key = None
            for k, v in params.items():
                if any(s in k.lower() for s in ["subnet", "network", "link", "tunnel_subnet"]):
                    if isinstance(v, str) and "/" in v and "." in v:
                        subnet_val = v
                        subnet_key = k
                        break

            if subnet_val:
                try:
                    net = ipaddress.ip_network(subnet_val, strict=False)
                    hosts = list(net.hosts())
                    if len(hosts) >= len(devices):
                        for d_idx, dev in enumerate(devices):
                            dev_name = getattr(dev, "name", f"Device{d_idx+1}")
                            assigned_ip = str(hosts[d_idx])
                            peer_idx = 1 if d_idx == 0 else 0
                            peer_ip = str(hosts[peer_idx])

                            proposed_params[dev_name]["assigned_interface_ip"] = (
                                f"{assigned_ip}/{net.prefixlen}"
                            )
                            proposed_params[dev_name]["peer_ip"] = peer_ip
                            proposed_params[dev_name]["peer_interface_ip"] = peer_ip
                            proposed_params[dev_name]["interconnect_subnet"] = subnet_val
                except Exception as e:
                    logger.warning(f"Could not compute peer IP allocations: {e}")

        return NetworkMasterPlan(
            proposed_parameters=proposed_params,
            deployment_sequence=sequence,
            rationale="Deterministic plan generated from structured intent parameters and topology rules.",
        )

    def verify_alignment(
        self, configs: dict[str, Any], constraints: list[InteroperabilityConstraint]
    ) -> dict[str, Any]:
        """
        Performs a post-generation check to see if all configs respected the constraints.
        """
        report: dict[str, Any] = {"is_compatible": True, "discrepancies": []}

        for device_name, data in configs.items():
            config_text = data.get("config", "").lower()
            for c in constraints:
                val_str = str(c.value).lower()
                # Use word boundaries to avoid false positives (e.g., VLAN 1 vs Gig0/10)
                if not re.search(rf"\b{re.escape(val_str)}\b", config_text):
                    report["is_compatible"] = False
                    report["discrepancies"].append(
                        {
                            "device": device_name,
                            "parameter": c.parameter_name,
                            "expected": val_str,
                            "issue": f"Shared parameter '{c.parameter_name}' mismatch.",
                        }
                    )

        return report
