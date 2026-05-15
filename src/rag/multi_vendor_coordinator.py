from typing import Dict, Any, List, Optional, cast
import re
import json
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

    proposed_parameters: Dict[str, Dict[str, Any]] = Field(
        description="Map of device name -> parameter dictionary"
    )
    deployment_sequence: List[str] = Field(
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
    ) -> List[InteroperabilityConstraint]:
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
        constraints: List[InteroperabilityConstraint],
        master_plan: Optional[NetworkMasterPlan] = None,
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
                    prompt += f"{i+1}. {step}\n"

            prompt += f"\nPLANNING RATIONALE: {master_plan.rationale}\n"

        if prompt:
            prompt += "\nFailure to follow these constraints will result in a Tier 3 Functional Error.\n"

        return prompt

    def generate_interop_plan(self, intent: Any) -> NetworkMasterPlan:
        """
        Uses an LLM to pre-calculate a consistent network plan for all devices.
        This ensures that dynamically assigned IPs, ASNs, and IDs match across peers.
        """
        from langchain_core.prompts import ChatPromptTemplate
        from src.llm import LLMProvider

        logger.info("Generating global interoperability plan...")

        planning_llm = LLMProvider.get_structured_llm(NetworkMasterPlan, temperature=0)

        prompt = ChatPromptTemplate.from_template(
            "You are a Senior Network Architect planning a multi-device configuration.\n"
            "Task 1: Given the intent, propose consistent IP addresses, AS numbers, and IDs for ALL involved devices.\n"
            "Ensure that peer interfaces on the same link are in the same subnet (e.g. .1 and .2).\n"
            "CRITICAL: Always provide a subnet mask or prefix (e.g. /24 or 255.255.255.0) for EVERY proposed IP address.\n\n"
            "Task 2: Define a logical DEPLOYMENT SEQUENCE (step-by-step) to ensure functional correctness "
            "(e.g. 1. Enable interfaces, 2. Configure IPs, 3. Routing protocols).\n\n"
            "INTENT: {intent_text}\n"
            "PARAMETERS: {params}\n"
            "DEVICES: {devices}\n\n"
            "Output the plan strictly in the requested JSON format."
        )

        chain = prompt | planning_llm

        try:
            device_info = [{"name": d.name, "vendor": d.vendor} for d in intent.devices]
            plan = cast(
                NetworkMasterPlan,
                chain.invoke(
                    {
                        "intent_text": intent.original_text,
                        "params": json.dumps(intent.parameters),
                        "devices": json.dumps(device_info),
                    }
                ),
            )
            return plan
        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                raise e
            logger.error(f"Failed to generate interop plan: {e}")
            return NetworkMasterPlan(
                proposed_parameters={},
                deployment_sequence=[],
                rationale="Fallback: Plan generation failed.",
            )

    def verify_alignment(
        self, configs: Dict[str, Any], constraints: List[InteroperabilityConstraint]
    ) -> Dict[str, Any]:
        """
        Performs a post-generation check to see if all configs respected the constraints.
        """
        report: Dict[str, Any] = {"is_compatible": True, "discrepancies": []}

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
