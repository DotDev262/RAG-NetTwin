import os
import json
import time
import hashlib
from typing import List, Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.llm import LLMProvider
import dspy
from src.schemas.intent import StructuredIntent, BatchStructuredIntent, ActionType
from src.parser.inventory_resolver import InventoryResolver
from src.rag.vector_store import VectorStore
from src.utils import setup_logger

logger = setup_logger("IntentParser")

# Cache for parsed intents to avoid redundant API calls
INTENT_CACHE_FILE = "data/processed/intent_cache.json"


def with_retry(max_retries=5, initial_sleep=2):
    """
    Decorator for exponential backoff on RateLimitErrors.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    e_str = str(e).lower()
                    if "rate_limit" in e_str or "429" in e_str:
                        retries += 1
                        sleep_time = initial_sleep * (2 ** (retries - 1))
                        logger.warning(
                            f"Rate limit hit. Retrying in {sleep_time}s... ({retries}/{max_retries})"
                        )
                        time.sleep(sleep_time)
                    else:
                        raise e
            return func(*args, **kwargs)  # Last try

        return wrapper

    return decorator


class IntentSignature(dspy.Signature):
    """
    Translate a natural language network intent into a structured JSON-like format.
    You must identify the protocol, action, target devices, and all critical parameters.
    """

    intent = dspy.InputField(desc="The natural language intent from the user.")
    context = dspy.InputField(desc="Relevant examples or documentation snippets.")

    protocol = dspy.OutputField(desc="Primary network protocol (e.g., OSPF, BGP).")
    action = dspy.OutputField(
        desc="Allowed values: 'create', 'update', 'delete', 'verify', etc."
    )
    devices = dspy.OutputField(
        desc="List of devices with 'name', 'vendor', and 'os_type'."
    )
    parameters = dspy.OutputField(
        desc="Dictionary of key-value parameters (e.g., area, as_number)."
    )
    requirements = dspy.OutputField(desc="List of constraints (e.g., no_downtime).")


class DSPyIntentParser(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_intent = dspy.ChainOfThought(IntentSignature)

    def forward(self, intent, context=""):
        return self.generate_intent(intent=intent, context=context)


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

        # Load cache
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Loads processed intents from disk."""
        if os.path.exists(INTENT_CACHE_FILE):
            try:
                with open(INTENT_CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load intent cache: {e}")
        return {}

    def _save_cache(self):
        """Saves processed intents to disk."""
        os.makedirs(os.path.dirname(INTENT_CACHE_FILE), exist_ok=True)
        try:
            with open(INTENT_CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save intent cache: {e}")

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

    @with_retry(max_retries=3)
    def _parse_chunk(self, texts: List[str]) -> List[StructuredIntent]:
        """Parse a single chunk of intents with retry logic and caching."""
        # 1. Separate texts into cached and non-cached
        results = {}  # index -> intent
        to_parse_texts = []
        to_parse_indices = []

        for idx, text in enumerate(texts):
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            if text_hash in self.cache:
                results[idx] = StructuredIntent(**self.cache[text_hash])
            else:
                to_parse_texts.append(text)
                to_parse_indices.append(idx)

        if not to_parse_texts:
            return [results[i] for i in range(len(texts))]

        # 2. Parse non-cached intents in a batch
        actions_str = ", ".join([f"'{action.value}'" for action in ActionType])
        count = len(to_parse_texts)

        # Recommendation 2: Dynamic Few-Shot Retrieval (use first intent in chunk as anchor)
        few_shot_examples = self.vector_store.retrieve_few_shot(
            to_parse_texts[0], n_results=3
        )
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
                (
                    "human",
                    "Parse these {{num}} intents into a JSON list:\n{{input_list}}",
                ),
            ],
            template_format="jinja2",
        )

        input_list = "\n".join([f"{i + 1}. {t}" for i, t in enumerate(to_parse_texts)])
        chain = prompt | self.batch_llm
        batch_result = chain.invoke({"input_list": input_list, "num": count})

        if len(batch_result.intents) != count:
            raise ValueError(
                f"LLM returned {len(batch_result.intents)} intents but expected {count}"
            )

        # 3. Merge results and save to cache
        for i, intent in enumerate(batch_result.intents):
            intent.original_text = to_parse_texts[i]
            # Assign a unique ID if missing
            if not intent.intent_id:
                intent.intent_id = hashlib.sha256(
                    intent.original_text.encode()
                ).hexdigest()[:12]

            self._resolve_device_metadata(intent)

            # Save to cache
            text_hash = hashlib.sha256(intent.original_text.encode()).hexdigest()
            self.cache[text_hash] = intent.model_dump()

            results[to_parse_indices[i]] = intent

        self._save_cache()
        return [results[i] for i in range(len(texts))]

    def parse(self, text: str) -> StructuredIntent:
        """Translates NL text to StructuredIntent object using DSPy."""
        # 1. Check Local Cache (Hash-based)
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        if text_hash in self.cache:
            logger.info(f"Intent local cache hit: {text[:30]}...")
            return StructuredIntent(**self.cache[text_hash])

        # Efficiency Phase 1: Check Semantic Cache
        cached_intent_dict = self.vector_store.check_intent_parsing_cache(text)
        if cached_intent_dict:
            logger.info(f"Intent semantic cache hit: {text[:30]}...")
            intent = StructuredIntent(**cached_intent_dict)
            # Ensure the hash is updated in the local cache too
            self.cache[text_hash] = intent.model_dump()
            return intent

        # 2. Dynamic Few-Shot Retrieval
        few_shot_examples = self.vector_store.retrieve_few_shot(text, n_results=3)
        examples_str = ""
        for i, ex in enumerate(few_shot_examples):
            examples_str += f"\nExample {i+1}:\nNL: \"{ex['intent']}\"\nStructured: {ex['structured']}\n"

        # 3. Use Compiled DSPy Logic
        try:
            # Wrap the actual DSPy call with retry logic
            result = self._dspy_parse(text, examples_str)
        except Exception as e:
            logger.error(f"DSPy parsing failed: {e}. Falling back to standard LLM.")
            result = self._legacy_parse(text, examples_str)

        # Assign unique ID
        if not result.intent_id:
            result.intent_id = text_hash[:12]

        # 4. Save to Cache
        intent_dump = result.model_dump()
        self.cache[text_hash] = intent_dump
        self._save_cache()

        # Efficiency Phase 1: Update Semantic Cache
        self.vector_store.update_intent_parsing_cache(text, intent_dump)

        return result

    @with_retry(max_retries=5)
    def _dspy_parse(self, text: str, examples_str: str) -> StructuredIntent:
        """Internal DSPy call with retry logic."""
        response = self.dspy_parser(intent=text, context=examples_str)

        # Helper to safely parse lists/dicts from strings
        import ast

        def safe_eval(val, default_type):
            if not val:
                return [] if isinstance(default_type, list) else {}

            parsed = val
            if isinstance(val, str):
                try:
                    # Clean up common LLM string artifacts
                    cleaned_val = val.replace("```json", "").replace("```", "").strip()
                    parsed = ast.literal_eval(cleaned_val)
                except Exception:
                    parsed = val

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
            requirements=safe_eval(response.requirements, []),
        )
        self._resolve_device_metadata(intent)
        return intent

    @with_retry(max_retries=5)
    def _legacy_parse(self, text: str, examples_str: str) -> StructuredIntent:
        """Original LangChain-based parsing logic (Fallback) with retry logic."""
        actions_str = ", ".join([f"'{action.value}'" for action in ActionType])
        system_prompt = f"""You are a network automation expert. Translate the following natural language intent into a structured JSON format for Intent-Based Networking.

{IntentParser.VENDOR_DETECTION_INSTRUCTIONS}

You MUST choose the most specific 'action' from the following allowed values: {actions_str}.
Populate the 'requirements' list with any relevant constraints.

### FEW-SHOT EXAMPLES ###
{examples_str}
"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
            ],
            template_format="jinja2",
        )

        chain = prompt | self.structured_llm
        intent = chain.invoke({"input": text})

        intent.original_text = text
        self._resolve_device_metadata(intent)
        return intent

    def _resolve_device_metadata(self, intent: StructuredIntent):
        """Enhances device intents with data from the inventory resolver."""
        for i, device in enumerate(intent.devices):
            # Ensure name is never null
            if not device.name:
                device.name = f"Device-{i+1}"

            # Get metadata from inventory
            metadata = self.inventory_resolver.resolve(device.name)

            # Only override if hostname was actually found in inventory
            if metadata.get("found_in_inventory", False):
                # Recommendation: Only override vendor if LLM didn't strongly identify one
                # OR if the inventory is considered the "source of truth"
                # For this project, we prioritize inventory if found.
                device.vendor = metadata.get("vendor", device.vendor)
                device.os_type = metadata.get("os_type", device.os_type)
                device.os_version = metadata.get("os_version", device.os_version)
            else:
                # No inventory match - use LLM-detected values or smart defaults
                if not device.vendor:
                    # Smart fallback based on protocol context or text
                    text_lower = (intent.original_text or "").lower()
                    if "juniper" in text_lower or "junos" in text_lower:
                        device.vendor = "juniper"
                    else:
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
