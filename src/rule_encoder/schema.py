"""
Core Schema Definitions for LLM-Assisted Rule Encoder.

Defines the formal, machine-readable Alignment Schema Rules, vendor syntax mappings,
and interoperability constraints extracted from RFCs and vendor documentation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConstraintType(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    SUBNET_MATCH = "SUBNET_MATCH"
    RANGE_MATCH = "RANGE_MATCH"
    RECIPROCAL_PEER = "RECIPROCAL_PEER"
    ASYMMETRIC_PERMISSIBLE = "ASYMMETRIC_PERMISSIBLE"


class ParameterDataType(str, Enum):
    INTEGER = "INTEGER"
    STRING = "STRING"
    IP_ADDRESS = "IP_ADDRESS"
    IP_PREFIX = "IP_PREFIX"
    BOOLEAN = "BOOLEAN"


class InteroperabilityConstraint(BaseModel):
    """Formal interoperability constraint rule between connected devices."""
    constraint_type: ConstraintType = Field(
        description="Type of invariant enforcement (e.g. EXACT_MATCH across link, RECIPROCAL_PEER for BGP)"
    )
    scope: str = Field(
        default="SHARED_LINK",
        description="Scope of applicability: SHARED_LINK, AS_WIDE, TOPOLOGY_GLOBAL"
    )
    description: str = Field(
        description="Formal description of the inter-vendor invariant rule"
    )
    is_mandatory: bool = Field(
        default=True,
        description="Whether a violation causes adjacency/session formation failure"
    )


class VendorSyntaxMapping(BaseModel):
    """Syntax and configuration command representation for a specific network vendor."""
    vendor: str = Field(description="Vendor name: cisco, juniper, arista, etc.")
    os_type: str = Field(description="OS name: ios-xe, junos, etc.")
    command_template: str = Field(
        description="CLI command template or pattern (e.g., 'ip ospf hello-interval <value>' or 'set protocols ospf area <area> hello-interval <value>')"
    )
    submode_path: Optional[str] = Field(
        default=None,
        description="Hierarchy or mode where command belongs (e.g. 'interface', 'router ospf <pid>')"
    )
    default_value: Optional[Any] = Field(
        default=None,
        description="Standard default value in this vendor CLI if unstated"
    )
    value_format_notes: Optional[str] = Field(
        default=None,
        description="Notes on vendor formatting nuances (e.g., dotted decimal vs decimal area)"
    )


class AlignmentSchemaRule(BaseModel):
    """
    Formal, machine-readable Alignment Schema Rule for a protocol parameter.
    """
    rule_id: str = Field(description="Unique deterministic ID (e.g. OSPF_HELLO_INTERVAL_01)")
    protocol_name: str = Field(description="Standard Protocol Name: OSPFv2, OSPFv3, BGP, etc.")
    parameter_identifier: str = Field(
        description="Canonical identifier: area_id, hello_interval, dead_interval, md5_key_id, remote_as, mtu"
    )
    data_type: ParameterDataType = Field(
        default=ParameterDataType.INTEGER,
        description="Data type of parameter (INTEGER, STRING, IP_ADDRESS, etc.)"
    )
    allowed_range: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional boundary range (e.g. {'min': 1, 'max': 65535})"
    )
    vendor_syntax: Dict[str, VendorSyntaxMapping] = Field(
        description="Map of vendor name ('cisco', 'juniper') to its CLI syntax mapping"
    )
    interoperability_constraint: InteroperabilityConstraint = Field(
        description="Cross-vendor interoperability constraint requirement"
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="RFC or vendor reference specification citation (e.g., 'RFC 2328 Section 9.5')"
    )


class AlignmentRuleSet(BaseModel):
    """Container for a collection of extracted alignment rules."""
    protocol: str
    version: str = "1.0.0"
    source_document: str
    rules: List[AlignmentSchemaRule] = Field(default_factory=list)


class AlignmentRegistry(BaseModel):
    """Top-level registry structure containing validated alignment rules."""
    registry_version: str = "2.0.0"
    description: str = "Compiled cross-vendor protocol parameter alignment registry for RAG-NetTwin v2."
    protocols: Dict[str, List[AlignmentSchemaRule]] = Field(default_factory=dict)
