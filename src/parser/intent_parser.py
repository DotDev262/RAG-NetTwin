import os
import json
import time
import hashlib
import threading
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_core.prompts import ChatPromptTemplate
from src.llm import LLMProvider
import dspy
from src.schemas.intent import StructuredIntent, BatchStructuredIntent, ActionType
from src.parser.inventory_resolver import InventoryResolver
from src.rag.vector_store import VectorStore
from src.utils import setup_logger
from src.utils.helpers import with_retry

logger = setup_logger("IntentParser")

# Cache for parsed intents to avoid redundant API calls
INTENT_CACHE_FILE = "data/processed/intent_cache.json"


class IntentSignature(dspy.Signature):
    """
    Translate a natural language network intent into a structured JSON-like format.
    You must identify the protocol, action, target devices, and all critical parameters.
    """

    intent = dspy.InputField(desc="The natural language intent from the user.")
    context = dspy.InputField(desc="Relevant examples or documentation snippets.")

    protocol = dspy.OutputField(desc="Primary network protocol (e.g., OSPF, BGP).")
    action = dspy.OutputField(
        desc="Allowed values: 'create', 'update', 'delete', 'apply', 'add', 'remove', 'verify', etc."
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
- If the text mentions multiple vendors (e.g. "between Cisco and Juniper"), you MUST create separate device objects for each vendor.
- If a device name is mentioned (e.g. Router-A), try to infer its vendor from the surrounding text or the inventory context.
- Default to "cisco" only if NO other vendor is mentioned in the entire intent.
- Use "cisco" for IOS, IOS-XE, NX-OS.
- Use "juniper" for JunOS, MX, EX, QFX.
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
        self.cache_lock = threading.Lock()
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
        with self.cache_lock:
            os.makedirs(os.path.dirname(INTENT_CACHE_FILE), exist_ok=True)
            try:
                with open(INTENT_CACHE_FILE, "w") as f:
                    json.dump(self.cache, f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save intent cache: {e}")

    def parse_batch(
        self, texts: List[str], chunk_size: int = 5
    ) -> List[StructuredIntent]:
        """Translates a batch of NL texts into StructuredIntent objects in parallel chunks."""
        all_intents_map = {}  # original index -> intent

        chunks = []
        for i in range(0, len(texts), chunk_size):
            chunks.append((i, texts[i : i + chunk_size]))

        # Limit concurrency to avoid overwhelming the LLM and hitting rate limits too fast
        max_workers = min(len(chunks), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(self._parse_chunk, chunk_texts): (idx, chunk_texts)
                for idx, chunk_texts in chunks
            }

            for future in as_completed(future_to_chunk):
                start_idx, chunk_texts = future_to_chunk[future]
                try:
                    intents = future.result()
                    for j, intent in enumerate(intents):
                        all_intents_map[start_idx + j] = intent
                except Exception as e:
                    logger.warning(
                        f"Chunk starting at index {start_idx} failed ({e}), falling back to sequential for chunk..."
                    )
                    # Fallback to sequential for this chunk only
                    for j, text in enumerate(chunk_texts):
                        time.sleep(1.0)  # Add delay to avoid rate limiting during fallback
                        all_intents_map[start_idx + j] = self.parse(text)

        return [all_intents_map[i] for i in range(len(texts))]

    @with_retry(max_retries=5)
    def _parse_chunk(self, texts: List[str]) -> List[StructuredIntent]:
        """Parse a single chunk of intents with retry logic and caching."""
        # 1. Separate texts into cached and non-cached
        results = {}  # index -> intent
        to_parse_texts = []
        to_parse_indices = []

        with self.cache_lock:
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
        with self.cache_lock:
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
        with self.cache_lock:
            if text_hash in self.cache:
                logger.info(f"Intent local cache hit: {text[:30]}...")
                return StructuredIntent(**self.cache[text_hash])

        # Efficiency Phase 1: Check Semantic Cache
        cached_intent_dict = self.vector_store.check_intent_parsing_cache(text)
        if cached_intent_dict:
            logger.info(f"Intent semantic cache hit: {text[:30]}...")
            intent = StructuredIntent(**cached_intent_dict)
            # Ensure the hash is updated in the local cache too
            with self.cache_lock:
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
        with self.cache_lock:
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
            if isinstance(default_type, list):
                if not isinstance(parsed, list):
                    parsed = [parsed] if parsed else []
                
                # Robust conversion of items to strings if required
                if default_type and isinstance(default_type[0], str):
                    stringified = []
                    for item in parsed:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                stringified.append(f"{k}: {v}")
                        else:
                            stringified.append(str(item))
                    return stringified

            return parsed

        intent = StructuredIntent(
            original_text=text,
            protocol=response.protocol,
            action=response.action,
            devices=safe_eval(response.devices, [{}]),
            parameters=safe_eval(response.parameters, {}),
            requirements=safe_eval(response.requirements, [""]),
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
