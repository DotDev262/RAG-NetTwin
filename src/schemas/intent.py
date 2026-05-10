from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
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


class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(
        description="Unique identifier for the intent", default=None
    )
    protocol: Optional[str] = Field(
        description="Network protocol involved, e.g., OSPF, BGP, Static, ACL, Interface",
        default="Unknown",
    )
    action: ActionType = Field(
        description="Specific operation: create, update, delete, enable, disable, configure, apply, add, remove, show, verify, monitor",
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


class BatchStructuredIntent(BaseModel):
    intents: List[StructuredIntent] = Field(description="List of structured intents")
