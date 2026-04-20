from typing import Dict, Any, List, Optional
import json
import re
from pydantic import BaseModel
from utils import setup_logger

logger = setup_logger("MultiVendorCoordinator")

class InteroperabilityConstraint(BaseModel):
    """
    Represents a shared parameter that must match across different vendors.
    """
    parameter_name: str
    value: Any
    protocol: str
    importance: str = "CRITICAL"

class MultiVendorCoordinator:
    """
    Coordinates configuration consistency across heterogeneous vendors (Recommendation 2).
    Addresses RQ3: Semantic correctness in multi-vendor environments.
    """

    def __init__(self):
        # Maps intent parameters to their interoperability equivalents
        # Example: Cisco 'area' == Juniper 'area'
        self.interop_map = {
            "ospf": ["area", "process_id", "hello_interval", "dead_interval"],
            "bgp": ["local_as", "remote_as", "peer_group", "hold_time"],
            "vlan": ["vlan_id", "vlan_name"],
            "interface": ["mtu", "speed", "duplex"]
        }

    def extract_shared_constraints(self, intent: Any) -> List[InteroperabilityConstraint]:
        """
        Identifies parameters in the intent that must be consistent across all devices.
        """
        constraints = []
        protocol = (intent.protocol or "").lower()
        params = intent.parameters or {}

        if protocol in self.interop_map:
            for param_key in self.interop_map[protocol]:
                if param_key in params:
                    constraints.append(InteroperabilityConstraint(
                        parameter_name=param_key,
                        value=params[param_key],
                        protocol=protocol
                    ))
        
        # Generic parameter extraction for cross-vendor logic
        # e.g., if 'ip' is mentioned, we might need subnet consistency (future enhancement)
        
        return constraints

    def build_coordination_prompt(self, constraints: List[InteroperabilityConstraint]) -> str:
        """
        Generates a prompt snippet to force the LLM to respect shared constraints.
        """
        if not constraints:
            return ""

        prompt = "\n### MULTI-VENDOR INTEROPERABILITY CONSTRAINTS ###\n"
        prompt += "To ensure the network functions correctly across different vendors, you MUST use these exact values:\n"
        for c in constraints:
            prompt += f"- {c.protocol.upper()} {c.parameter_name}: {c.value}\n"
        prompt += "Failure to match these values will result in a functional validation error.\n"
        return prompt

    def verify_alignment(self, configs: Dict[str, Any], constraints: List[InteroperabilityConstraint]) -> Dict[str, Any]:
        """
        Performs a post-generation check to see if all configs respected the constraints.
        """
        report = {"is_compatible": True, "discrepancies": []}
        
        for device_name, data in configs.items():
            config_text = data.get("config", "").lower()
            for c in constraints:
                val_str = str(c.value).lower()
                # Use word boundaries to avoid false positives (e.g., VLAN 1 vs Gig0/10)
                if not re.search(rf"\b{re.escape(val_str)}\b", config_text):
                    report["is_compatible"] = False
                    report["discrepancies"].append({
                        "device": device_name,
                        "parameter": c.parameter_name,
                        "expected": val_str,
                        "issue": f"Shared parameter '{c.parameter_name}' mismatch."
                    })
                    
        return report
