"""
Configuration Generation Module for RAG-NetTwin.

This module handles the generation of network device configurations from
structured intents using a RAG (Retrieval-Augmented Generation) approach.
It retrieves relevant documentation from ChromaDB and uses an LLM to generate
vendor-specific CLI commands.

Key Features:
- Vendor-aware generation (Cisco IOS-XE vs Juniper JunOS)
- Version-locked retrieval for accurate syntax
- Structured output with citations for hallucination mitigation
- Fallback chain for robust retrieval

Typical Usage:
    from src.parser.intent_parser import IntentParser
    from src.rag.config_generator import ConfigGenerator

    parser = IntentParser()
    generator = ConfigGenerator()
    intent = parser.parse("Configure OSPF on Router-A")
    config = generator.generate(intent)
"""

from typing import List, Dict, Any, Optional, cast
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.rag.vector_store import VectorStore
from src.rag.parameter_normalizer import ParameterNormalizer
from src.rag.query_expander import QueryExpander
from src.validation.referential_integrity import ReferentialIntegrityValidator
from src.rag.multi_vendor_coordinator import MultiVendorCoordinator
from src.evaluation.hallucination_detector import HallucinationDetector
from src.schemas.intent import StructuredIntent
from src.llm import LLMProvider
from src.utils import clean_cli_prose, setup_logger, with_retry
from src.config import settings

CONFIG_GENERATOR_VERSION = "2.4.0"  # Incremented for Hierarchical Anchoring
logger = setup_logger("ConfigGenerator")


class CommandBlock(BaseModel):
    """
    A block of CLI commands grounded in specific documentation.
    """

    commands: List[str] = Field(description="List of raw CLI configuration commands")
    source_ids: List[str] = Field(
        description="IDs from the DOCUMENTATION block that justify these specific commands. "
        "Leave empty if the command is a generic prerequisite (like 'configure terminal').",
        default_factory=list,
    )


class DeviceConfigOutput(BaseModel):
    """
    Pydantic model for structured configuration output.
    """

    blocks: List[CommandBlock] = Field(
        description="List of command blocks, each with its own documentation sources"
    )
    confidence_score: float = Field(
        description="Confidence score (0.0 to 1.0) of the generated config", ge=0, le=1
    )
    reasoning_path: str = Field(
        description="Step-by-step reasoning for the chosen commands. NEVER leave this empty or null.",
        default="",
    )
    verification_commands: List[str] = Field(
        description="CLI commands to verify the configuration works (e.g., show ip ospf neighbor)",
        default_factory=list,
    )
    explanation: Optional[str] = Field(
        description="Brief summary of the changes", default=""
    )


class ConfigGenerator:
    """
    Generates network device configurations using RAG and LLM.

    This class orchestrates the configuration generation process by:
    1. Checking if the intent is "lite" (simple, doesn't need RAG retrieval)
    2. Retrieving relevant documentation from ChromaDB based on vendor/version
    3. Using an LLM with structured output to generate CLI commands
    4. Adding citation comments to the config for hallucination traceability

    The generation supports both Cisco IOS-XE and Juniper JunOS syntax,
    with automatic fallback to ensure retrieval always returns some results.

    Attributes:
        llm: Base LLM for refinement tasks (temperature=0 for deterministic output).
        structured_llm: LLM configured with DeviceConfigOutput schema for
            structured generation with citations and confidence scores.
        vector_store: ChromaDB client for retrieval.

    Note:
        Caching is handled at the evaluation level (run_paper_eval.py) to ensure
        consistency with --clear-cache flag and research integrity. This class
        does not implement caching directly.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        vector_store: Optional[VectorStore] = None,
        coordinator: Optional[MultiVendorCoordinator] = None,
    ):
        """
        Initialize the ConfigGenerator.

        Args:
            model_name: Optional model name override.
            vector_store: Optional pre-instantiated VectorStore.
            coordinator: Optional pre-instantiated MultiVendorCoordinator.
        """
        self.llm = LLMProvider.get_llm(model=model_name, temperature=0.0)
        self.structured_llm = LLMProvider.get_structured_llm(
            schema=DeviceConfigOutput, model=model_name, temperature=0.0
        )
        self.vector_store = vector_store or VectorStore()
        self.coordinator = coordinator or MultiVendorCoordinator()
        self.hallucination_detector = HallucinationDetector()
        self.query_expander = QueryExpander(model_name=model_name)
        self._sanity_lock = threading.Lock()
        # Cache for query expansions to avoid repeated LLM calls
        self._query_expansion_cache: dict[str, list[str]] = {}

    def generate(
        self, structured_intent: StructuredIntent, retrieval_mode: str = "tiered"
    ) -> Dict[str, Any]:
        """
        Generates CLI configuration for each device.
        retrieval_mode: 'tiered' (ours), 'flat' (standard top-k), or 'none' (baseline).
        """
        # TEMPORARY: Clear semantic cache for fresh generation during debugging
        # This will be removed once generation is stable.
        self.vector_store.clear_cache()

        configs: Dict[str, Any] = {}
        # Deep Trace: Initialize trace dictionary
        trace: Dict[str, Any] = {
            "base_query": "",
            "expanded_queries": [],
            "retrieval_results": {},
            "llm_calls": {},
        }

        # Recommendation 3: Intent Sanity Check
        configs["_sanity_check"] = {"is_grounded": True, "warnings": []}

        is_lite: bool = self._check_lite_intent(structured_intent)
        if retrieval_mode == "none":
            is_lite = True  # Force baseline for ablation

        # Recommendation 2 (Multi-Vendor): Extract shared constraints and generate plan
        constraints = self.coordinator.extract_shared_constraints(structured_intent)

        master_plan: Optional[Any] = None
        if len(structured_intent.devices) > 1:
            master_plan = self.coordinator.generate_interop_plan(structured_intent)
            trace["master_plan"] = (
                master_plan.model_dump()
                if hasattr(master_plan, "model_dump")
                else master_plan
            )

        coordination_prompt: str = self.coordinator.build_coordination_prompt(
            constraints, master_plan=master_plan
        )

        # Build query once for all devices
        semantic_params: List[str] = []
        for k, v in structured_intent.parameters.items():
            semantic_params.append(k)
            if isinstance(v, str) and not re.match(r"^[0-9.:/]+$", v) and len(v) > 2:
                semantic_params.append(v)

        base_query: str = (
            f"{structured_intent.protocol} {structured_intent.action} "
            + " ".join(semantic_params)
        )
        trace["base_query"] = base_query

        # 1. Group devices by vendor + version
        device_groups: Dict[tuple[Optional[str], str], List[Any]] = {}
        for device in structured_intent.devices:
            group_key: tuple[Optional[str], str] = (
                device.vendor,
                self._normalize_version(device),
            )
            if group_key not in device_groups:
                device_groups[group_key] = []
            device_groups[group_key].append(device)

        # Phase 2: Multi-Query Expansion (Adaptive)
        # We start with just the base query and only expand if retrieval is poor.
        queries: List[str] = [base_query]
        expansion_triggered: bool = False
        trace["expanded_queries"] = queries

        # Cache for query expansions to avoid repeated LLM calls
        if not hasattr(self, "_query_expansion_cache"):
            self._query_expansion_cache = {}

        full_context_map: Dict[str, Dict[str, Any]] = {}

        # 2. Retrieval Phase
        if not is_lite:
            for (vendor, search_version), devices in device_groups.items():
                # Recommendation 5: Check Semantic Cache first
                if retrieval_mode != "none":
                    vendor_str: str = vendor if vendor else "unknown"
                    intent_text: str = structured_intent.original_text or ""

                    cached_response: Optional[Dict[str, Any]] = (
                        self.vector_store.check_cache(
                            intent_text,
                            structured_intent.parameters,
                            vendor_str,
                            retrieval_mode=retrieval_mode,
                        )
                    )

                    if cached_response:
                        logger.info(f"Semantic Cache Hit for vendor {vendor_str}!")
                        for dev in devices:
                            configs[dev.name] = cached_response
                        continue

                # Efficiency Phase 2: Pilot Retrieval & Adaptive Expansion
                if not expansion_triggered and retrieval_mode != "none":
                    # Quick check: how good is the base query?
                    pilot = self.vector_store.hybrid_retrieve(
                        query=base_query,
                        vendor=vendor,
                        os_version=search_version,
                        n_results=1,
                    )
                    # If distance > 0.60, documentation match is weak, trigger LLM expansion (Recommendation 4)
                    # Increased threshold to reduce unnecessary expansions
                    if not pilot or pilot[0].get("distance", 1.0) > 0.60:
                        logger.info(
                            f"Low confidence pilot search for {vendor}. Triggering Multi-Query Expansion..."
                        )
                        # Use cached expansion if available
                        cache_key = f"{base_query}:{vendor}:{search_version}"
                        if cache_key in self._query_expansion_cache:
                            queries = self._query_expansion_cache[cache_key]
                            logger.info(f"Using cached query expansion for {vendor}")
                        else:
                            queries = self.query_expander.expand(base_query)
                            self._query_expansion_cache[cache_key] = queries
                        trace["expanded_queries"] = queries
                        expansion_triggered = True
                    else:
                        logger.info(
                            f"High confidence pilot search for {vendor} (dist: {pilot[0].get('distance'):.2f}). Skipping expansion."
                        )

                results: List[Dict[str, Any]] = []

                # Accumulate results from available queries
                all_candidates: List[Dict[str, Any]] = []
                for q in queries:
                    if retrieval_mode == "tiered":
                        syntax_candidates = self.vector_store.hybrid_retrieve(
                            query=q,
                            vendor=vendor,
                            os_version=search_version,
                            tier=1,
                            n_results=3,
                        )
                        concept_candidates = self.vector_store.hybrid_retrieve(
                            query=q,
                            vendor=vendor,
                            os_version=search_version,
                            tier=2,
                            n_results=3,
                        )
                        all_candidates.extend(syntax_candidates)
                        all_candidates.extend(concept_candidates)

                    elif retrieval_mode == "graph":
                        # Phase 3: GraphRAG Retrieval (Recommendation 4)
                        # 1. Start with high-quality syntax seeds
                        seed_chunks = self.vector_store.hybrid_retrieve(
                            query=q,
                            vendor=vendor,
                            os_version=search_version,
                            tier=1,
                            n_results=3,
                        )
                        # 2. Expand using Knowledge Graph Communities (SOTA)
                        graph_chunks = self.vector_store.retrieve_community_context(
                            seed_chunks
                        )
                        all_candidates.extend(graph_chunks)

                    elif retrieval_mode == "flat":
                        flat_candidates = self.vector_store.hybrid_retrieve(
                            query=q,
                            vendor=vendor,
                            os_version=search_version,
                            n_results=5,
                        )
                        all_candidates.extend(flat_candidates)

                # Deduplicate candidates by ID
                unique_candidates_map: Dict[str, Dict[str, Any]] = {
                    str(c["id"]): c for c in all_candidates
                }
                unique_candidates: List[Dict[str, Any]] = list(
                    unique_candidates_map.values()
                )

                # Use Reranker
                if unique_candidates:
                    results = self.vector_store.rerank(
                        base_query, unique_candidates, n_results=6
                    )

                # Trace retrieval details
                for dev in devices:
                    trace["retrieval_results"][dev.name] = [
                        {
                            "id": r.get("id"),
                            "tier": r.get("metadata", {}).get("tier"),
                            "distance": r.get("distance"),
                            "rerank_score": r.get("rerank_score"),
                            "text_preview": (
                                str(r.get("text"))[:100] if r.get("text") else ""
                            ),
                        }
                        for r in results
                    ]

                if results:
                    distances: List[float] = [
                        float(res.get("distance") or 1.0) for res in results
                    ]
                    avg_distance: float = sum(distances) / len(results)
                    if avg_distance > 1.2:
                        warning: str = f"Authoritative documentation for '{structured_intent.protocol}' not found for {vendor}. Hallucination risk is high."
                        with self._sanity_lock:
                            configs["_sanity_check"]["warnings"].append(warning)
                            configs["_sanity_check"]["is_grounded"] = False
                else:
                    warning = f"No documentation found in KB for {vendor}/{search_version} '{structured_intent.protocol}'."
                    with self._sanity_lock:
                        configs["_sanity_check"]["warnings"].append(warning)
                        configs["_sanity_check"]["is_grounded"] = False

                if results:
                    results = self.vector_store.retrieve_with_parents(results)

                # 3. Dynamic Few-Shot Selection (Efficiency Recommendation 2)
                vendor_str = vendor if vendor else "unknown"

                # Determine few-shot count based on pilot confidence
                # If distance < 0.2, documentation is authoritative, no few-shot needed.
                # If distance < 0.4, 1 few-shot is enough.
                # Otherwise, use full 2 few-shots.
                pilot_dist = pilot[0].get("distance", 1.0) if pilot else 1.0
                n_few_shot = 2
                if pilot_dist < 0.2:
                    n_few_shot = 0
                elif pilot_dist < 0.4:
                    n_few_shot = 1

                gold_examples: List[Dict[str, Any]] = []
                if n_few_shot > 0:
                    gold_examples = self.vector_store.retrieve_gold_configs(
                        query=base_query, vendor=vendor_str, n_results=n_few_shot
                    )
                    logger.info(
                        f"Dynamic Few-Shot: Selected {len(gold_examples)} examples (pilot dist: {pilot_dist:.2f})"
                    )
                else:
                    logger.info(
                        f"Dynamic Few-Shot: Bypassing examples (pilot dist: {pilot_dist:.2f})"
                    )

                for dev in devices:
                    full_context_map[dev.name] = {
                        "chunks": results,
                        "examples": gold_examples,
                    }
        else:
            logger.info(f"Lite-RAG path activated (Retrieval Mode: {retrieval_mode}).")

        # 3. Generation Phase: Sequential (to avoid rate limits)
        futures: List[Any] = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            for device in structured_intent.devices:
                if device.name in configs:
                    continue

                device_context: str = ""
                valid_ids: List[str] = []
                examples: List[Dict[str, Any]] = []

                # Recommendation: Handle Lite intents by providing a base knowledge anchor
                if is_lite:
                    valid_ids = ["BASE_CLI_KNOWLEDGE"]

                if device.name in full_context_map:
                    data = full_context_map[device.name]
                    device_context = self.distill_context(data["chunks"])
                    valid_ids = [str(c.get("id")) for c in data["chunks"]]
                    # Add community labels to valid_ids (Recommendation 4)
                    for c in data["chunks"]:
                        comm = c.get("metadata", {}).get("graph_community")
                        if comm:
                            valid_ids.append(str(comm))
                    examples = data["examples"]

                futures.append(
                    executor.submit(
                        self._generate_single_device,
                        device,
                        structured_intent,
                        device_context,
                        coordination_prompt,
                        valid_ids,
                        examples,
                        master_plan=master_plan,
                    )
                )

            for future in as_completed(futures):
                try:
                    res: Dict[str, Any] = future.result()
                    device_name: str = str(res["device_name"])

                    # Extract trace from device result if present
                    if "_device_trace" in res:
                        trace["llm_calls"][device_name] = res.pop("_device_trace")

                    configs[device_name] = res

                    if res.get("config") != "ERROR":
                        device_obj = next(
                            d
                            for d in structured_intent.devices
                            if d.name == device_name
                        )
                        vendor_str = (
                            device_obj.vendor if device_obj.vendor else "unknown"
                        )
                        intent_text = structured_intent.original_text or ""

                        self.vector_store.update_cache(
                            intent_text,
                            structured_intent.parameters,
                            vendor_str,
                            res,
                            retrieval_mode=retrieval_mode,
                            version=CONFIG_GENERATOR_VERSION,
                        )
                except Exception as e:
                    if "429" in str(e) or "rate_limit" in str(e).lower():
                        logger.error(f"Rate limit hit in background thread: {e}")
                        raise e
                    logger.error(f"Thread execution failed: {e}")
                    # Continue for other devices, but this device will be missing from configs

        alignment_report = self.coordinator.verify_alignment(configs, constraints)
        configs["_interoperability_report"] = alignment_report

        # Phase 3: Referential Integrity Pre-Validation
        for device_name, data in configs.items():
            if device_name.startswith("_") or data.get("config") == "ERROR":
                continue

            device_obj = next(
                d for d in structured_intent.devices if d.name == device_name
            )
            ref_issues = ReferentialIntegrityValidator.check_config(
                data["config"], vendor=device_obj.vendor or "cisco"
            )
            if ref_issues:
                with self._sanity_lock:
                    configs["_sanity_check"]["warnings"].extend(ref_issues)
                    # We mark as ungrounded if referential integrity is broken
                    configs["_sanity_check"]["is_grounded"] = False

        configs["_trace"] = trace

        return configs

    @with_retry(max_retries=5)
    def _generate_single_device(
        self,
        device: Any,
        structured_intent: StructuredIntent,
        device_context: str,
        coordination_prompt: str = "",
        valid_source_ids: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        master_plan: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Generates configuration for a single device with a refinement loop.
        """
        # Format gold standard examples
        examples_str = ""
        if examples:
            examples_str = "\n### REFERENCE EXAMPLES (GOLD STANDARD) ###\n"
            for i, ex in enumerate(examples):
                examples_str += f"Example {i + 1}:\nIntent: {ex['intent']}\nConfig:\n{ex['config']}\n\n"

        # Phase 1: Syntactic Formatting Hints
        formatting_hints = ParameterNormalizer.normalize_ip_parameters(
            structured_intent.parameters, device.vendor
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Expert {vendor} {os_version} CLI specialist. "
                    "RULES: 1. Use {vendor} syntax ONLY. 2. NEVER mix vendors. 3. RESPECT shared constraints.\n\n"
                    "### ZERO TOLERANCE FOR HALLUCINATION ###\n"
                    "- NEVER add commands that are not explicitly mentioned in the documentation or required for the specific intent.\n"
                    "- NEVER invent IP addresses, VLAN IDs, or names that are not in the Intent or Parameters.\n"
                    "- If a command is not found in the documentation, DO NOT invent it based on general knowledge unless it is a standard prerequisite (like 'configure terminal').\n"
                    "- If the intent is to 'Enable OSPF', DO NOT also configure BGP or static routes 'just in case'.\n\n"
                    "### STRICT HIERARCHY RULES ###\n"
                    "- Global commands (hostname, logging) go at the top level.\n"
                    "- Interface commands (ip address, service-policy) MUST be within an 'interface <name>' block.\n"
                    "- QoS commands (set dscp, bandwidth) MUST be within a 'class <name>' block, which MUST be inside a 'policy-map <name>' block. NEVER place them directly under policy-map.\n"
                    "- ALL sub-mode commands (under interface, router, class, etc.) MUST be indented with exactly TWO spaces for visual hierarchy.\n"
                    "- Protocol commands (network, neighbor) MUST be within a 'router <protocol>' block.\n\n"
                    "### ATOMIC QOS BLOCKS (MANDATORY STRUCTURE) ###\n"
                    "1. ACL: 'access-list 101 permit ospf any any'\n"
                    "2. CLASS-MAP: 'class-map match-all CS6_CLASS' -> MUST be followed by ' match access-group 101'\n"
                    "3. POLICY-MAP: 'policy-map QoS_POLICY' -> MUST be followed by ' class CS6_CLASS' -> MUST be followed by '  set dscp 48'\n"
                    "4. INTERFACE: 'interface Ethernet0/0' -> MUST be followed by ' service-policy output QoS_POLICY'\n\n"
                    "### STRICT GROUNDING RULE ###\n"
                    "- ONLY use commands and syntax found in the ### DOCUMENTATION ### section.\n"
                    "- If the documentation shows a specific value range or example value, ADHERE to it.\n"
                    "- DO NOT use 'common knowledge' syntax if it differs from the provided documentation.\n"
                    "- If a requested command is not in the documentation, and is not a basic prerequisite (like 'configure terminal' or 'enable'), EXCLUDE it and explain why in the 'explanation'.\n\n"
                    "### PARAMETER INTEGRITY (CRITICAL) ###\n"
                    "- ONLY use IP addresses, ASNs, and identifiers provided in the 'Parameters' or 'Intent'.\n"
                    "- DO NOT invent complex network topologies or extra neighbors not mentioned in the intent.\n"
                    "- If the intent asks for a specific neighbor, ONLY configure that neighbor.\n"
                    "- If a parameter is missing, use a standard default (e.g. 10.0.0.1, GigabitEthernet0/1) but NEVER invent a pool of multiple random IPs.\n\n"
                    "### TOP FAILURE PATTERNS (FORBIDDEN) ###\n"
                    "- FORBIDDEN: 'no' commands (e.g., 'no ip address', 'no router ospf'). The environment starts from a clean state. DO NOT clear existing configuration.\n"
                    "- FORBIDDEN: 'ip address X.X.X.X ...' at global level. MUST be under interface.\n"
                    "- FORBIDDEN: 'service-policy ...' at global level. MUST be under interface.\n"
                    "- FORBIDDEN: Referencing an ACL name/number without defining it.\n\n"
                    "### REFERENTIAL INTEGRITY RULE ###\n"
                    "- If you reference an ACL, policy-map, route-map, or NAT pool, you MUST define it in the SAME output.\n"
                    "- Ensure the output 'device_name' EXACTLY matches the requested 'device_name'.\n\n"
                    "### COMMON SYNTAX CORRECTIONS (STRICT) ###\n"
                    "- CISCO OS: Use Traditional IOS / IOS-XE syntax ONLY. NEVER use 'type qos' or 'type traffic' (NX-OS/XR leakage).\n"
                    "- CISCO OSPF: Use 'ip ospf database-filter all out' (with hyphen and 'out'), NOT 'ip ospf database filter all'.\n"
                    "- CISCO NAT: Always use 'ip nat inside source list <acl> interface <int> overload' (must include the word 'inside'), NOT 'ip nat source list...'.\n"
                    "- CISCO NETFLOW (Flexible NetFlow): 1. Define 'flow record <name>' (match ipv4 source/dest, collect counter bytes/packets). 2. Define 'flow exporter <name>' (destination <ip>, transport udp <port>). 3. Define 'flow monitor <name>' (record <name>, exporter <name>). 4. Apply 'ip flow monitor <name> input' on interface.\n"
                    "- CISCO QoS (Structural): 1. 'access-list 101 permit ospf any any'. 2. 'class-map CS6_CLASS' (match access-group 101). 3. 'policy-map QoS_POLICY'. 4. Inside 'policy-map', you MUST use 'class CS6_CLASS'. 5. Inside 'class', use 'set dscp 48'. 6. Apply 'service-policy output QoS_POLICY' under 'interface Ethernet0/0'.\n"
                    "- VYOS (For 'juniper' in this lab): Use 'set interfaces ethernet eth1 address X.X.X.X/24', 'set protocols ospf area 0 network X.X.X.X/24', 'set protocols ospf area 0 hello-interval 5'.\n"
                    "- CISCO LACP: 1. Define 'interface port-channel 1'. 2. Under member interfaces, use 'channel-group 1 mode active'. Use 'EthernetX/Y' for interfaces (e.g., Ethernet0/1).\n"
                    "- JUNIPER OSPF: Use 'set protocols ospf area <area> interface <int>' syntax.\n"
                    "- BGP: Ensure 'address-family' is used if multi-protocol (IPv4/IPv6) is involved. For Cisco, use 'neighbor <ip> remote-as <asn>'.\n"
                    "- VPN: For Cisco Site-to-Site, define: crypto isakmp policy, crypto isakmp key, crypto ipsec transform-set, crypto map, and interface tunnel.\n"
                    "- PLACEHOLDERS: NEVER use 'Unknown'. If a parameter is missing, use standard defaults: Interface 'Ethernet0/0' (Cisco IOU) or 'ge-0/0/0' (Juniper), IP '10.0.0.1'.\n\n"
                    "### STRICT ISOLATION RULE ###\n"
                    "Generate output ONLY for device: {device_name}.\n\n"
                    "{coordination_prompt}",
                ),
                (
                    "human",
                    "### TASK ###\n"
                    "Device: {device_name} ({vendor} {os_version})\n"
                    "Intent: {intent_text}\n"
                    "Parameters: {intent_params}\n\n"
                    "{examples_str}"
                    "{formatting_hints}"
                    "### DOCUMENTATION ###\n"
                    "{device_context}\n\n"
                    "### INSTRUCTIONS ###\n"
                    "1. Use provided documentation for syntax. Ground each command block in source IDs.\n"
                    "2. CRITICAL: For citations, use ONLY the exact string found inside [SOURCE_ID: ...]. DO NOT include the 'SOURCE_ID:' prefix or the brackets themselves.\n"
                    "3. DO NOT use the word 'Unknown' for parameters. If an IP or interface is missing, use a standard default (e.g., GigabitEthernet0/1, 10.0.0.1).\n"
                    "4. Ensure all referenced entities (ACLs, policies, route-maps) are DEFINED in the output.\n"
                    "5. Translate all parameters accurately.",
                ),
            ]
        )

        try:
            # 1. First Pass: Structured Generation
            chain = prompt | self.structured_llm

            lite_context = device_context or (
                "No specific documentation chunks found. "
                "Use your [SOURCE_ID: BASE_CLI_KNOWLEDGE] and expertise for standard CLI syntax."
            )

            llm_input = {
                "intent_params": json.dumps(
                    structured_intent.parameters, separators=(",", ":")
                ),
                "intent_text": structured_intent.original_text,
                "device_context": lite_context,
                "device_name": device.name,
                "vendor": device.vendor,
                "os_version": device.os_version or "latest",
                "coordination_prompt": coordination_prompt,
                "examples_str": examples_str,
                "formatting_hints": formatting_hints,
            }

            from pydantic import ValidationError

            try:
                output: DeviceConfigOutput = cast(
                    DeviceConfigOutput, chain.invoke(llm_input)
                )
            except ValidationError as ve:
                logger.warning(
                    f"Structured synthesis ValidationError: {ve}. Triggering unstructured fallback..."
                )

                # Fallback: simplified unstructured prompt
                fallback_prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "You are a Senior Network Engineer for {vendor} {os_version}.\n"
                            "CRITICAL: Output ONLY raw CLI commands. Do not write explanations or conversational text.\n"
                            "Synthesize the commands to accomplish the intent using target documentation syntax.",
                        ),
                        (
                            "human",
                            "Device: {device_name}\n"
                            "Intent: {intent_text}\n"
                            "Parameters: {intent_params}\n"
                            "DOCUMENTATION:\n{device_context}\n\n"
                            "RAW CLI CONFIGURATION:",
                        ),
                    ]
                )

                fallback_chain = fallback_prompt | self.llm
                fallback_input = {
                    "device_name": device.name,
                    "vendor": device.vendor,
                    "os_version": device.os_version or "latest",
                    "intent_text": structured_intent.original_text,
                    "intent_params": json.dumps(structured_intent.parameters),
                    "device_context": lite_context,
                }

                fallback_response = fallback_chain.invoke(fallback_input)
                raw_config_text = clean_cli_prose(cast(str, fallback_response.content))

                # Build mock DeviceConfigOutput to integrate with down-stream verification
                output = DeviceConfigOutput(
                    blocks=[
                        CommandBlock(
                            commands=[
                                cmd.strip()
                                for cmd in raw_config_text.splitlines()
                                if cmd.strip()
                            ],
                            source_ids=["BASE_CLI_KNOWLEDGE"],
                        )
                    ],
                    confidence_score=0.5,
                    reasoning_path="Pydantic validation failure. Fell back to unstructured CLI synthesis.",
                    verification_commands=[],
                    explanation="Unstructured generation fallback.",
                )

            # Extract combined config and clean citations
            all_commands = []
            seen_commands = set()
            all_citations = []
            for block in output.blocks:
                for cmd in block.commands:
                    # Deduplicate and limit (Fix F14: Loopy LLM protection)
                    clean_cmd = cmd.strip()
                    if clean_cmd and clean_cmd not in seen_commands:
                        all_commands.append(clean_cmd)
                        seen_commands.add(clean_cmd)
                    if len(all_commands) > 200:  # Safety break
                        break

                if block.source_ids:
                    for cid in block.source_ids:
                        # Clean up common LLM citation errors
                        clean_cid = (
                            cid.replace("SOURCE_ID:", "")
                            .replace("ID:", "")
                            .replace("[", "")
                            .replace("]", "")
                            .strip()
                        )
                        # Fix F15: Strip sub-keys from BASE_CLI_KNOWLEDGE
                        if clean_cid.startswith("BASE_CLI_KNOWLEDGE"):
                            clean_cid = "BASE_CLI_KNOWLEDGE"

                        if clean_cid:
                            all_citations.append(clean_cid)

            # Final sanity check for "ERROR" tokens in commands (Fix F16)
            original_command_count = sum(len(b.commands) for b in output.blocks)
            all_commands = [c for c in all_commands if c.strip() != "ERROR"]

            if not all_commands:
                logger.warning(
                    f"LLM returned no valid commands for {device.name}. "
                    f"Original count: {original_command_count}, "
                    f"Reasoning: {output.reasoning_path}"
                )
                config_text = "ERROR"
            else:
                config_text = "\n".join(all_commands)

            # 2. Refinement Loop: Static Analysis (Batfish + Referential Integrity)
            from src.validation.batfish_validator import BatfishValidator
            from src.validation.referential_integrity import (
                ReferentialIntegrityValidator,
            )

            validator = BatfishValidator()

            # Determine refinement limit based on intent complexity
            max_refinements = self._get_refinement_limit(structured_intent)
            current_config = config_text

            for i in range(max_refinements):
                # Check for syntax/logic with Batfish
                val_res = validator.validate(
                    {device.name: current_config}, structured_intent
                )

                # Check for broken references locally (more robust for ACLs/Policies)
                ref_issues = ReferentialIntegrityValidator.check_config(
                    current_config, vendor=device.vendor or "cisco"
                )

                # Step 4: Audit for Hallucinations (Zero-Tolerance)
                hal_report = self.hallucination_detector.detect(
                    config=current_config,
                    citations=list(set(all_citations)),
                    valid_source_ids=valid_source_ids or [],
                    retrieved_texts=[device_context],
                    intent_context=structured_intent.original_text or "",
                    intent_params=structured_intent.parameters,
                    master_plan=master_plan.model_dump()
                    if (master_plan and hasattr(master_plan, "model_dump"))
                    else master_plan,
                )

                # Check if we should stop refinement (PASS/WARNING are acceptable)
                has_critical_issues = False
                if val_res["status"] in ["FAIL", "REJECT_FOR_MANUAL_REVIEW"]:
                    # Filter out purely informational or ignored gaps
                    remaining_issues = [
                        i
                        for i in val_res.get("issues", [])
                        if i.get("type") not in ["CONFIG_WARNING", "IGNORED"]
                    ]
                    if remaining_issues:
                        has_critical_issues = True

                if (
                    not has_critical_issues
                    and not ref_issues
                    and not hal_report.is_hallucinated
                ):
                    break

                # Aggregate feedback
                feedback_parts = []
                if val_res.get("issues"):
                    for issue in val_res["issues"]:
                        details = issue["details"]
                        if "Unknown" in details:
                            details += " (CRITICAL: DO NOT use the word 'Unknown'. Replace with a sensible default like GigabitEthernet0/1 or 10.0.0.1)"
                        feedback_parts.append(details)
                if ref_issues:
                    for issue in ref_issues:
                        feedback_parts.append(
                            issue
                            + " (CRITICAL: You MUST define this entity in your output. Example: 'access-list 101 permit any' or 'route-map MY-MAP permit 10')"
                        )

                if hal_report.is_hallucinated:
                    feedback_parts.append(
                        f"HALLUCINATION DETECTED: {hal_report.reason}. "
                        "CRITICAL: Remove any ungrounded commands or unauthorized parameters immediately. "
                        "ONLY use parameters explicitly mentioned in the intent."
                    )

                error_feedback = "\n".join(feedback_parts)
                logger.info(
                    f"Refining {device.name} (Attempt {i + 1}) due to: {error_feedback[:100]}..."
                )

                current_config = self.refine(
                    device_name=device.name,
                    config=current_config,
                    error_feedback=error_feedback,
                    vendor=device.vendor,
                    os_version=device.os_version,
                )

            # Final post-processing (Recommendation 5)
            current_config = ParameterNormalizer.post_process_config(
                current_config, vendor=device.vendor
            )

            return {
                "device_name": device.name,
                "config": current_config,
                "explanation": output.explanation,
                "verification_commands": output.verification_commands,
                "retrieved_sources": list(set(all_citations)),
                "blocks": [b.model_dump() for b in output.blocks],
                "valid_source_ids": valid_source_ids or [],
                "grounding_context": device_context,
                "confidence": output.confidence_score,
                "reasoning": output.reasoning_path,
            }

        except Exception as e:
            if "429" in str(e) or "rate_limit" in str(e).lower():
                raise e
            logger.error(f"Generation failed for {device.name}: {e}")
            return {"device_name": device.name, "config": "ERROR", "error": str(e)}

    def distill_context(
        self, raw_chunks: List[Dict[str, Any]], token_limit: int = 1500
    ) -> str:
        """
        Token Efficiency (Rec 4): Strips noise from PDF chunks using regex.
        Extracts ONLY CLI blocks and key configuration context.
        Also applies 'Lost-in-the-Middle' reordering (Phase 3).
        Enforces a hard token limit (Estimated) to prevent prompt bloat.
        Identifies and prioritizes CRITICAL VENDOR RESTRICTIONS (Negative Grounding).
        """
        # Phase 3: Reorder chunks to put most relevant at edges
        raw_chunks = self.vector_store.reorder_lost_in_the_middle(raw_chunks)

        restrictions: List[str] = []
        distilled: str = ""
        current_token_est = 0

        # Regex to find CLI blocks (Improved: Allow leading symbols/numeric starts/more keywords)
        cli_pattern = re.compile(
            r"(?m)^[\s\t•*-]*(?:no\s+)?(?:interface|router|ip|ipv6|switchport|vlan|access-list|ntp|logging|snmp|set|firewall|protocols|routing-options|system|neighbor|description|hostname|address-family|peer-group|permit|deny|area|network|route-reflector-client|neighbor|server|peer|policy-options|autonomous-system|as-path|community-list|prefix-list|bgp|ospf|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|[0-9]{1,5})\b.*$",
            re.IGNORECASE,
        )

        # Phase 3: Negative Grounding keywords
        restriction_keywords = [
            "caution",
            "warning",
            "restriction",
            "important",
            "must not",
            "not supported",
            "limitation",
        ]

        for res in raw_chunks:
            text: str = str(res.get("text", ""))
            chunk_id: str = str(res.get("id"))
            lines = text.splitlines()

            # 1. Extract Restrictions (Negative Grounding)
            for line in lines:
                if any(k in line.lower() for k in restriction_keywords):
                    restrictions.append(f"[Ref: {chunk_id}] {line.strip()}")

            # Token limit check for main content
            if current_token_est > token_limit:
                continue

            # 2. Extract CLI lines
            cli_lines: List[str] = cli_pattern.findall(text)

            # 3. Extract prose that looks like a definition or example
            prose_context: List[str] = []
            for line in lines:
                if any(
                    k in line.lower()
                    for k in [
                        "is used to",
                        "specifies",
                        "defines",
                        "mandatory",
                        "for example",
                        "example:",
                        "syntax:",
                    ]
                ):
                    prose_context.append(line.strip())

            if cli_lines or prose_context:
                # Hierarchical Anchoring (Recommendation 1)
                hierarchy_str = ""
                raw_h = res.get("metadata", {}).get("command_hierarchy")
                if raw_h:
                    try:
                        h_list = json.loads(str(raw_h))
                        if h_list:
                            hierarchy_str = " > ".join(h_list)
                    except Exception:
                        pass

                # Community Anchoring (GraphRAG Optimization)
                community_str = ""
                comm_label = res.get("metadata", {}).get("graph_community")
                if comm_label:
                    community_str = f"[SOURCE_ID: {comm_label}] (Community Anchor)\n"

                chunk_str = f"[SOURCE_ID: {chunk_id}]\n"
                if community_str:
                    chunk_str += community_str
                if hierarchy_str:
                    chunk_str += f"DOCUMENTATION_PATH: {hierarchy_str}\n"
                if cli_lines:
                    chunk_str += "CLI_SYNTAX:\n" + "\n".join(cli_lines[:15]) + "\n"
                if prose_context:
                    chunk_str += "USAGE_RULES:\n" + "\n".join(prose_context[:5]) + "\n"
                chunk_str += "---\n"

                distilled += chunk_str
                # Conservative estimate for CLI/Code: 1 token per 3 characters (Fix F9)
                current_token_est += len(chunk_str) // 3

        # Combine: Restrictions go FIRST
        final_output = ""
        if restrictions:
            final_output += "!!! CRITICAL VENDOR RESTRICTIONS !!!\n"
            final_output += "\n".join(restrictions[:5]) + "\n\n"

        final_output += distilled
        return final_output

    def _check_lite_intent(self, intent: StructuredIntent) -> bool:
        """
        Heuristic to identify simple intents that don't need RAG retrieval.

        Lite intents are simple operations that use standard, well-known commands
        and don't require documentation lookup. These include:
        - Show/verify commands (display-only, no config changes)
        - Simple hostname/description/banner tasks
        - Basic interface enabling (no complex params)
        - NTP/Logging basics

        Args:
            intent: StructuredIntent to check.

        Returns:
            True if the intent is simple enough to skip RAG retrieval,
            False otherwise.
        """
        lite_actions = ["show", "verify", "enable", "disable"]
        if intent.action.value in lite_actions:
            # For enable/disable, only skip RAG if no complex protocol is involved
            if not intent.protocol or intent.protocol.lower() in [
                "interface",
                "lldp",
                "snmp",
            ]:
                return True

        # Simple administrative tasks (Efficiency Recommendation 4)
        boilerplate_protocols = [
            "hostname",
            "description",
            "banner",
            "ntp",
            "logging",
            "timezone",
            "clock",
            "alias",
        ]
        if intent.protocol and intent.protocol.lower() in boilerplate_protocols:
            return True

        return False

    def _get_refinement_limit(self, intent: StructuredIntent) -> int:
        """
        Determine appropriate refinement limit based on intent complexity.
        Simple intents get fewer refinements to save API calls.
        Complex intents get more refinements to ensure quality.

        Returns:
            int: Number of refinement attempts allowed (0-2)
        """
        if not getattr(settings, "enable_self_correction", True):
            return 0

        # Simple intents: minimal or no refinement needed
        simple_protocols = [
            "hostname",
            "description",
            "banner",
            "ntp",
            "logging",
            "timezone",
            "clock",
            "alias",
            "snmp",
            "lldp",
        ]

        # Check if it's a simple administrative task
        if intent.protocol and str(intent.protocol).lower() in simple_protocols:
            return 0

        # Check for simple actions with minimal parameters
        if hasattr(intent.action, "value"):
            action_value = intent.action.value
        else:
            action_value = str(intent.action)

        if action_value in ["enable", "disable", "show", "verify"]:
            # Only allow refinement if there are complex parameters
            complex_params = [
                "bgp",
                "ospf",
                "vrrp",
                "dhcp",
                "nat",
                "vpn",
                "qos",
                "netflow",
            ]
            if not any(
                param in str(intent.parameters).lower() for param in complex_params
            ):
                return 1  # Limited refinement for basic actions

        # Complex intents that benefit from refinement
        complex_protocols = [
            "qos",
            "netflow",
            "ipfix",
            "bgp",
            "vrrp",
            "vpn",
            "ospf",
            "isis",
            "mpls",
            "pim",
        ]

        # Check for complex protocols or multi-device scenarios
        if intent.protocol and any(
            proto in str(intent.protocol).lower() for proto in complex_protocols
        ):
            return 2

        # Multiple devices often need more refinement for consistency
        if len(intent.devices) > 1:
            return 2

        # Check for complex parameters that often need refinement
        param_str = str(intent.parameters).lower()
        complex_indicators = [
            "access-list",
            "policy-map",
            "class-map",
            "route-map",
            "flow",
            "exporter",
            "monitor",
            "record",
            "bgp",
            "as-number",
            "neighbor",
            "vrrp",
            "vrf",
            "vrrp",
            "vrf",
            "multicast",
            "anycast",
        ]

        if any(indicator in param_str for indicator in complex_indicators):
            return 2

        # Default to 1 refinement for most cases
        return 1

    @with_retry(max_retries=5)
    def refine(
        self,
        device_name: str,
        config: str,
        error_feedback: str,
        vendor: str,
        os_version: Optional[str] = None,
    ) -> str:
        """
        Refines a configuration based on validation error feedback.
        """
        if os_version is None:
            os_version = "21.4" if vendor.lower() == "juniper" else "17.6"

        # Build prompt asking LLM to fix the configuration
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a CLI Debugger for {vendor} {os_version}.\n"
                    "CRITICAL: Output ONLY raw CLI commands. DO NOT output prose, conversational text, explanations, or 'should be changed to'.\n"
                    "Fix syntax errors using EXACT {vendor} {os_version} CLI syntax.\n"
                    "NEVER mix syntax from other vendors or versions.\n"
                    "### FORBIDDEN: DO NOT use 'no' commands (except 'no shutdown' if needed) to clear configurations (e.g., 'no ip address', 'no class-map', 'no policy-map', 'no interface'). Generate only the final desired state.",
                ),
                (
                    "human",
                    "Device: {device_name} ({vendor} {os_version})\n"
                    "ERRORS: {error_feedback}\n"
                    "CONFIG TO FIX:\n{config}\n\n"
                    "FIXED RAW CLI COMMANDS:",
                ),
            ]
        )

        response = (prompt | self.llm).invoke(
            {
                "device_name": device_name,
                "config": config,
                "error_feedback": error_feedback,
                "vendor": vendor,
                "os_version": os_version,
            }
        )

        return clean_cli_prose(cast(str, response.content))

    def _normalize_version(self, device) -> str:
        """
        Normalize OS version to match knowledge base format.
        """
        os_type = device.os_type
        vendor = (device.vendor or "cisco").lower()

        # Recommendation: If OS Type is Unknown, infer it from Vendor
        if not os_type or os_type.lower() == "unknown":
            os_type = "junos" if vendor == "juniper" else "ios-xe"

        os_version = device.os_version

        # Default to well-tested versions if not specified
        if not os_version:
            os_version = "21.4" if vendor == "juniper" else "17.6"

        # Map os_type to KB prefix
        type_prefix_map = {
            "ios-xe": "ios-xe",
            "junos": "junos",
            "ios": "ios",
            "nxos": "nxos",
            "eos": "eos",
        }

        prefix = type_prefix_map.get(os_type.lower(), os_type.lower())

        if os_version.startswith(prefix):
            return os_version

        return f"{prefix}-{os_version}"
