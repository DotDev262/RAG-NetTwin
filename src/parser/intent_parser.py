import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from config import settings
from llm import LLMProvider
import dspy
from enum import Enum
from parser.inventory_resolver import InventoryResolver
from rag.vector_store import VectorStore
from utils import setup_logger

logger = setup_logger("IntentParser")


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


class IntentSignature(dspy.Signature):
    """
    Translate a natural language network intent into a structured JSON-like format.
    You must identify the protocol, action, target devices, and all critical parameters.
    """
    intent = dspy.InputField(desc="The natural language intent from the user.")
    context = dspy.InputField(desc="Relevant examples or documentation snippets.")
    
    protocol = dspy.OutputField(desc="Primary network protocol (e.g., OSPF, BGP).")
    action = dspy.OutputField(desc="Allowed values: 'create', 'update', 'delete', 'verify', etc.")
    devices = dspy.OutputField(desc="List of devices with 'name', 'vendor', and 'os_type'.")
    parameters = dspy.OutputField(desc="Dictionary of key-value parameters (e.g., area, as_number).")
    requirements = dspy.OutputField(desc="List of constraints (e.g., no_downtime).")


class DSPyIntentParser(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_intent = dspy.ChainOfThought(IntentSignature)

    def forward(self, intent, context=""):
        return self.generate_intent(intent=intent, context=context)


class ActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    CONFIGURE = "configure"
    SHOW = "show"
    VERIFY = "verify"
    MONITOR = "monitor"


class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(
        description="Unique identifier for the intent", default=None
    )
    protocol: Optional[str] = Field(
        description="Network protocol involved, e.g., OSPF, BGP, Static, ACL, Interface",
        default="Unknown",
    )
    action: ActionType = Field(
        description="Specific operation: create, update, delete, enable, disable, configure, show, verify, monitor",
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


class IntentParser:
    """Parses natural language intents into structured JSON using LLM."""

    # Shared vendor detection instructions for consistency
    VENDOR_DETECTION_INSTRUCTIONS = """
IMPORTANT VENDOR DETECTION:
- If the text mentions "Cisco" or "cisco" anywhere, set vendor to "cisco"
- If the text mentions "Juniper" or "juniper" or "MX" or "EX", set vendor to "juniper"
- If no vendor is mentioned, default to "cisco"
- CRITICAL: Pay close attention to vendor mentions like "on Cisco", "for Juniper", "between Cisco and Juniper"
"""

    def __init__(self, model_name: Optional[str] = None):
        # Use LLMProvider to get structured LLM instance
        self.structured_llm = LLMProvider.get_structured_llm(
            schema=StructuredIntent, model=model_name, temperature=0
        )
        self.batch_llm = LLMProvider.get_structured_llm(
            schema=BatchStructuredIntent, model=model_name, temperature=0
        )
        self.inventory_resolver = InventoryResolver()
        self.vector_store = VectorStore()
        
        # Recommendation 3: Initialize DSPy Engine
        lm = LLMProvider.get_dspy_lm(model=model_name)
        dspy.settings.configure(lm=lm)
        self.dspy_parser = DSPyIntentParser()

    def parse_batch(
        self, texts: List[str], chunk_size: int = 3
    ) -> List[StructuredIntent]:
        """Translates a batch of NL texts into StructuredIntent objects in chunks."""
        all_intents = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            try:
                intents = self._parse_chunk(chunk)
                all_intents.extend(intents)
            except Exception as e:
                logger.warning(
                    f"Chunk {i // chunk_size + 1} failed ({e}), falling back to sequential for chunk..."
                )
                # Fallback to sequential for this chunk only
                for text in chunk:
                    all_intents.append(self.parse(text))

        return all_intents

    def _parse_chunk(self, texts: List[str]) -> List[StructuredIntent]:
        """Parse a single chunk of intents."""
        actions_str = ", ".join([f"'{action.value}'" for action in ActionType])
        count = len(texts)
        
        # Recommendation 2: Dynamic Few-Shot Retrieval (use first intent in chunk as anchor)
        few_shot_examples = self.vector_store.retrieve_few_shot(texts[0], n_results=3)
        examples_str = ""
        for i, ex in enumerate(few_shot_examples):
            examples_str += f"\nExample {i+1}:\nNL: \"{ex['intent']}\"\nStructured: {ex['structured']}\n"

        system_prompt = f"""You are a network automation expert. 
Translate the following list of {count} natural language intents into a structured JSON list.

{IntentParser.VENDOR_DETECTION_INSTRUCTIONS}

RULES:
1. You MUST return a list containing EXACTLY {count} intent objects.
2. For each intent, choose the most specific 'action' from the allowed values: {actions_str}.
3. The 'original_text' for each object MUST match the input text exactly from the provided list.

### FEW-SHOT EXAMPLES ###
{examples_str if examples_str else "No specific examples found."}
"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "Parse these {{num}} intents into a JSON list:\n{{input_list}}"),
            ],
            template_format="jinja2"
        )

        input_list = "\n".join([f"{i + 1}. {t}" for i, t in enumerate(texts)])
        chain = prompt | self.batch_llm
        batch_result = chain.invoke({"input_list": input_list, "num": count})

        # CRITICAL: Verify we got the same number of intents back
        if len(batch_result.intents) != len(texts):
            raise ValueError(
                f"LLM returned {len(batch_result.intents)} intents but expected {len(texts)}"
            )

        # CRITICAL: Force-overwrite original_text with EXACT input strings to avoid cache key mismatches
        for i, intent in enumerate(batch_result.intents):
            intent.original_text = texts[i]
            self._resolve_device_metadata(intent)

        return batch_result.intents

    def parse(self, text: str) -> StructuredIntent:
        """Translates NL text to StructuredIntent object using DSPy."""
        
        # Recommendation 2: Dynamic Few-Shot Retrieval
        few_shot_examples = self.vector_store.retrieve_few_shot(text, n_results=3)
        examples_str = ""
        for i, ex in enumerate(few_shot_examples):
            examples_str += f"\nExample {i+1}:\nNL: \"{ex['intent']}\"\nStructured: {ex['structured']}\n"

        # Recommendation 3: Use Compiled DSPy Logic
        try:
            response = self.dspy_parser(intent=text, context=examples_str)
            
            # Helper to safely parse lists/dicts from strings
            import ast
            def safe_eval(val, default_type):
                if not val: return [] if isinstance(default_type, list) else {}
                
                parsed = val
                if isinstance(val, str):
                    try: parsed = ast.literal_eval(val)
                    except: parsed = val
                
                # If we expect a list but got a single item (dict or string)
                if isinstance(default_type, list) and not isinstance(parsed, list):
                    return [parsed] if parsed else []
                
                return parsed

            intent = StructuredIntent(
                original_text=text,
                protocol=response.protocol,
                action=response.action,
                devices=safe_eval(response.devices, []),
                parameters=safe_eval(response.parameters, {}),
                requirements=safe_eval(response.requirements, [])
            )
            self._resolve_device_metadata(intent)
            return intent
        except Exception as e:
            logger.error(f"DSPy parsing failed: {e}. Falling back to standard LLM.")
            return self._legacy_parse(text, examples_str)

    def _legacy_parse(self, text: str, examples_str: str) -> StructuredIntent:
        """Original LangChain-based parsing logic (Fallback)."""
        actions_str = ", ".join([f"'{action.value}'" for action in ActionType])
        system_prompt = f"""You are a network automation expert. Translate the following natural language intent into a structured JSON format for Intent-Based Networking.

{IntentParser.VENDOR_DETECTION_INSTRUCTIONS}

You MUST choose the most specific 'action' from the following allowed values: {actions_str}.
Populate the 'requirements' list with any relevant constraints.

### FEW-SHOT EXAMPLES ###
{examples_str}
"""
        prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{{input}}"),
            ],
            template_format="jinja2"
        )
        chain = prompt | self.structured_llm
        intent = chain.invoke({"input": text})
        intent.original_text = text
        self._resolve_device_metadata(intent)
        return intent

    def _resolve_device_metadata(self, intent: StructuredIntent):
        """Enhances device intents with data from the inventory resolver."""
        for device in intent.devices:
            # Get metadata from inventory
            metadata = self.inventory_resolver.resolve(device.name)

            # Only override if hostname was actually found in inventory
            if metadata.get("found_in_inventory", False):
                device.vendor = metadata.get("vendor", device.vendor)
                device.os_type = metadata.get("os_type", device.os_type)
                device.os_version = metadata.get("os_version", device.os_version)
            else:
                # No inventory match - use LLM-detected values or smart defaults
                if not device.vendor:
                    device.vendor = "cisco"
                
                if not device.os_type:
                    device.os_type = "junos" if device.vendor == "juniper" else "ios-xe"
                
                if not device.os_version:
                    device.os_version = "21.4" if device.vendor == "juniper" else "17.6"


if __name__ == "__main__":
    # Quick test
    try:
        parser = IntentParser()
        test_text = "Enable OSPF process 10 on Router-A (Cisco IOS-XE 17.6) for interface Gig0/1 with IP 192.168.1.1/24, ensuring no downtime."
        result = parser.parse(test_text)
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Error: {e}")
