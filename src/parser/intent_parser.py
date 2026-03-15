import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from llm import LLMProvider
from enum import Enum
from parser.inventory_resolver import InventoryResolver


class DeviceIntent(BaseModel):
    name: str = Field(description="Name of the device, e.g., Router-A")
    vendor: Optional[str] = Field(
        description="Device vendor, e.g., cisco, juniper", default="cisco"
    )
    os_type: Optional[str] = Field(
        description="Operating system type, e.g., ios-xe, junos", default="ios-xe"
    )
    os_version: Optional[str] = Field(
        description="OS version, e.g., 17.6", default="17.6"
    )


class ActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    SHOW = "show"
    VERIFY = "verify"
    MONITOR = "monitor"


class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(
        description="Unique identifier for the intent", default=None
    )
    protocol: Optional[str] = Field(
        description="Network protocol involved, e.g., OSPF, BGP, Static, ACL, Interface"
    )
    action: ActionType = Field(
        description="Specific CRUD operation: create, update, delete, enable, disable, show, verify, monitor"
    )
    devices: List[DeviceIntent] = Field(
        description="List of devices involved in the intent"
    )
    parameters: Dict[str, Any] = Field(
        description="Key-value pairs of parameters, e.g., {'area': '0', 'ip': '192.168.1.1/24'}"
    )
    requirements: List[str] = Field(
        description="Specific requirements or goals, e.g., ['establish_adjacency', 'no_downtime', 'validate_only']"
    )
    original_text: Optional[str] = Field(
        description="The original natural language text", default=None
    )


class BatchStructuredIntent(BaseModel):
    intents: List[StructuredIntent] = Field(description="List of structured intents")


class IntentParser:
    """Parses natural language intents into structured JSON using LLM."""

    def __init__(self, model_name: Optional[str] = None):
        # Use LLMProvider to get structured LLM instance
        self.structured_llm = LLMProvider.get_structured_llm(
            schema=StructuredIntent, model=model_name, temperature=0
        )
        self.batch_llm = LLMProvider.get_structured_llm(
            schema=BatchStructuredIntent, model=model_name, temperature=0
        )
        self.inventory_resolver = InventoryResolver()

    def parse_batch(self, texts: List[str]) -> List[StructuredIntent]:
        """Translates a batch of NL texts into StructuredIntent objects in one call."""
        system_prompt = f"""You are a network automation expert. Translate the following list of natural language intents into a structured JSON list for Intent-Based Networking.

For each intent, you MUST choose the most specific 'action' from the allowed values: {", ".join([f"'{action.value}'" for action in ActionType])}.
Populate the 'original_text' field with the input string.
"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "Parse these intents into a list:\n{input_list}"),
            ]
        )

        input_list = "\n".join([f"{i + 1}. {t}" for i, t in enumerate(texts)])
        chain = prompt | self.batch_llm
        try:
            batch_result = chain.invoke({"input_list": input_list})
            # Apply inventory resolution for each intent
            for intent in batch_result.intents:
                self._resolve_device_metadata(intent)
            return batch_result.intents
        except Exception as e:
            # Fallback to individual parsing if batch fails
            print(f"      ⚠️  Batch parsing failed ({e}), falling back to individual...")
            return [self.parse(t) for t in texts]

    def parse(self, text: str) -> StructuredIntent:
        """Translates NL text to StructuredIntent object."""
        system_prompt = f"""You are a network automation expert. Translate the following natural language intent into a structured JSON format for Intent-Based Networking.

You MUST choose the most specific 'action' from the following allowed values: {", ".join([f"'{action.value}'" for action in ActionType])}.
Populate the 'requirements' list with any relevant constraints, such as 'no_downtime' if the user emphasizes minimal disruption, or 'validate_only' if the intent is purely for verification.

Examples:
Natural Language: "Create OSPF area 0 on Router-A for interface Gig0/1."
Structured Intent:
{{{{
  "protocol": "OSPF",
  "action": "create",
  "devices": [{{{{ "name": "Router-A", "vendor": "cisco", "os_type": "ios-xe", "os_version": "17.6" }}}}],
  "parameters": {{{{ "area": "0", "interface": "Gig0/1" }}}},
  "requirements": []
}}}}

Natural Language: "Remove BGP neighbor 10.0.0.2 from Router-B."
Structured Intent:
{{{{
  "protocol": "BGP",
  "action": "delete",
  "devices": [{{{{ "name": "Router-B", "vendor": "cisco", "os_type": "ios-xe", "os_version": "17.6" }}}}],
  "parameters": {{{{ "neighbor_ip": "10.0.0.2" }}}},
  "requirements": ["no_downtime"]
}}}}
"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ]
        )

        chain = prompt | self.structured_llm
        intent = chain.invoke({"input": text})
        intent.original_text = text  # Ensure this is set
        self._resolve_device_metadata(intent)
        return intent

    def _resolve_device_metadata(self, intent: StructuredIntent):
        """Enhances device intents with data from the inventory resolver."""
        for device in intent.devices:
            # Handle null values from LLM - provide sensible defaults
            if not device.vendor:
                device.vendor = "cisco"
            if not device.os_type:
                device.os_type = "ios-xe"
            if not device.os_version:
                device.os_version = "17.6"

            # Resolve if we have specific inventory data for that hostname
            metadata = self.inventory_resolver.resolve(device.name)

            # Inventory takes precedence for technical facts if the intent was vague
            # (e.g. didn't specify a version or use the 17.6 default)
            if (
                device.os_version
                and device.os_version == "17.6"
                and metadata.get("os_version") != "17.6"
            ):
                device.os_version = metadata["os_version"]
                device.vendor = metadata["vendor"]
                device.os_type = metadata["os_type"]


if __name__ == "__main__":
    # Quick test
    try:
        parser = IntentParser()
        test_text = "Enable OSPF process 10 on Router-A (Cisco IOS-XE 17.6) for interface Gig0/1 with IP 192.168.1.1/24, ensuring no downtime."
        result = parser.parse(test_text)
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
