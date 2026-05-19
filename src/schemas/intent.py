from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class DeviceIntent(BaseModel):
    name: Optional[str] = Field(
        description="Name of the device, e.g., Router-A. Default to 'Device' if unknown.",
        default="Device",
    )
    vendor: Optional[str] = Field(
        description="Device vendor, e.g., cisco, juniper", default=None
    )
    os_type: Optional[str] = Field(
        description="Operating system type, e.g., ios-xe, junos", default=None
    )
    os_version: Optional[str] = Field(
        description="OS version, e.g., 17.6, 21.4", default=None
    )


class ActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    CONFIGURE = "configure"
    SET = "set"
    SHOW = "show"
    VERIFY = "verify"
    MONITOR = "monitor"
    APPLY = "apply"
    ADD = "add"
    REMOVE = "remove"
    RESTRICT = "restrict"
    BLOCK = "block"
    ALLOW = "allow"
    PERMIT = "permit"
    DENY = "deny"


class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(
        description="Unique identifier for the intent", default=None
    )
    protocol: Optional[str] = Field(
        description="Network protocol involved, e.g., OSPF, BGP, Static, ACL, Interface",
        default="Unknown",
    )
    action: ActionType = Field(
        description="Specific operation: create, update, delete, enable, disable, configure, apply, add, remove, show, verify, monitor, restrict, block, allow, permit, deny",
        default=ActionType.CONFIGURE,
    )
    devices: List[DeviceIntent] = Field(
        description="List of devices involved in the intent",
        default_factory=list,
    )
    parameters: Dict[str, Any] = Field(
        description="Key-value pairs of parameters, e.g., {'area': '0', 'ip': '192.168.1.1/24'}",
        default_factory=dict,
    )
    requirements: List[str] = Field(
        description="Specific requirements or goals, e.g., ['establish_adjacency', 'no_downtime', 'validate_only']",
        default_factory=list,
    )
    original_text: Optional[str] = Field(
        description="The original natural language text", default=None
    )

    model_config = {"coerce_numbers_to_str": True}

    @model_validator(mode="before")
    @classmethod
    def validate_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        import ast
        import json

        # Handle parameters
        params = data.get("parameters")
        if isinstance(params, str) and params.strip():
            try:
                # Try JSON first
                cleaned = params.replace("'", '"')
                data["parameters"] = json.loads(cleaned)
            except Exception:
                try:
                    data["parameters"] = ast.literal_eval(params)
                except Exception:
                    pass

        # Handle requirements
        reqs = data.get("requirements")
        if isinstance(reqs, str) and reqs.strip():
            try:
                data["requirements"] = ast.literal_eval(reqs)
            except Exception:
                data["requirements"] = [reqs]

        # Handle devices
        devs = data.get("devices")
        if isinstance(devs, str) and devs.strip():
            try:
                data["devices"] = ast.literal_eval(devs)
            except Exception:
                pass

        return data


class BatchStructuredIntent(BaseModel):
    intents: List[StructuredIntent] = Field(description="List of structured intents")
