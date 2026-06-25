# Research Specification: RAG-NetTwin (Code Implementation Blueprint)

This document provides a highly technical, implementation-focused blueprint of the **RAG-NetTwin** framework. It maps core logical systems to their concrete python code snippets and algorithms, enabling another AI system to understand, reproduce, or build upon the architecture.

---

## 1. Intent Abstraction & Data Models

### 1.1 Data Schema
* **File**: [src/schemas/intent.py](file:///home/aryan/Projects/RAG-NetTwin/src/schemas/intent.py)

Pydantic V2 models define the boundary between unstructured user intents and structured topology parameter inputs. The [StructuredIntent](file:///home/aryan/Projects/RAG-NetTwin/src/schemas/intent.py#L43-111) model enforces typing and normalizes string inputs using pre-validators.

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from enum import Enum

class DeviceIntent(BaseModel):
    name: Optional[str] = Field(description="Name of the device, e.g., Router-A.", default="Device")
    vendor: Optional[str] = Field(description="Device vendor, e.g., cisco, juniper", default=None)
    os_type: Optional[str] = Field(description="Operating system type, e.g., ios-xe, junos", default=None)
    os_version: Optional[str] = Field(description="OS version, e.g., 17.6, 21.4", default=None)

class ActionType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    CONFIGURE = "configure"
    APPLY = "apply"
    SHOW = "show"
    # ... additional action types ...

class StructuredIntent(BaseModel):
    intent_id: Optional[str] = Field(description="Unique identifier", default=None)
    protocol: Optional[str] = Field(description="Network protocol involved, e.g., OSPF, BGP", default="Unknown")
    action: ActionType = Field(description="Operation type", default=ActionType.CONFIGURE)
    devices: List[DeviceIntent] = Field(description="List of target devices", default_factory=list)
    parameters: Dict[str, Any] = Field(description="Key-value configuration parameters", default_factory=dict)
    requirements: List[str] = Field(description="Specific configuration goals", default_factory=list)
    original_text: Optional[str] = Field(description="Raw intent string", default=None)

    model_config = {"coerce_numbers_to_str": True}

    @model_validator(mode="before")
    @classmethod
    def validate_strings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        import ast
        import json

        # Safely parse parameters if passed as a string representation
        params = data.get("parameters")
        if isinstance(params, str) and params.strip():
            try:
                data["parameters"] = json.loads(params.replace("'", '"'))
            except Exception:
                try:
                    data["parameters"] = ast.literal_eval(params)
                except Exception:
                    pass
        return data
```

---

## 2. Adaptive Retrieval & Query Logic

### 2.1 Pilot Search & Adaptive Query Expansion
* **File**: [src/rag/config_generator.py](file:///home/aryan/Projects/RAG-NetTwin/src/rag/config_generator.py)

In [ConfigGenerator.generate](file:///home/aryan/Projects/RAG-NetTwin/src/rag/config_generator.py#L135-212), pilot retrieval is triggered to inspect chunk distance before calling LLM expansion.

```python
# Extract from config_generator.py: Retrieval Phase
is_lite = self._check_lite_intent(structured_intent)
queries = [base_query]
expansion_triggered = False

if not is_lite:
    for (vendor, search_version), devices in device_groups.items():
        # Adaptive Multi-Query Expansion Gate
        if not expansion_triggered and retrieval_mode != "none":
            pilot = self.vector_store.hybrid_retrieve(
                query=base_query,
                vendor=vendor,
                os_version=search_version,
                n_results=1,
            )
            # Threshold Check: Cosine distance > 0.70 indicates a weak match
            if not pilot or pilot[0].get("distance", 1.0) > 0.70:
                logger.info("Low confidence pilot search. Triggering Multi-Query Expansion...")
                cache_key = f"{base_query}:{vendor}:{search_version}"
                if cache_key in self._query_expansion_cache:
                    queries = self._query_expansion_cache[cache_key]
                else:
                    queries = self.query_expander.expand(base_query)
                    self._query_expansion_cache[cache_key] = queries
                expansion_triggered = True
```

---

## 3. Hybrid Search & Sibling Community Routing

### 3.1 Metadata Filtering & Chroma Querying
* **File**: [src/rag/vector_store.py](file:///home/aryan/Projects/RAG-NetTwin/src/rag/vector_store.py)

The vector search constructs logical `where` filters to match target firmware and OS types.

```python
# Extract from vector_store.py: retrieve()
where_conditions: List[Dict[str, Any]] = []
if vendor:
    where_conditions.append({"vendor": vendor})
if os_version:
    # Explicit version-locking filter
    where_conditions.append({"os_version": os_version})
if tier:
    where_conditions.append({"tier": tier})

where_clause: Optional[Dict[str, Any]] = None
if len(where_conditions) == 1:
    where_clause = where_conditions[0]
elif len(where_conditions) > 1:
    where_clause = {"$and": where_conditions}

# Manually compute embeddings and query ChromaDB
query_embeddings = self.model.encode([query], convert_to_numpy=True).tolist()
results = self.collection.query(
    query_embeddings=query_embeddings, 
    n_results=n_results, 
    where=where_clause
)
```

### 3.2 Community-Aware GraphRAG Retrieval
* **File**: [src/rag/vector_store.py](file:///home/aryan/Projects/RAG-NetTwin/src/rag/vector_store.py)

This method expands context from seed chunks by pulling structural documentation neighbors while applying pruning rules.

```python
# Extract from vector_store.py: retrieve_community_context()
def retrieve_community_context(
    self, seed_chunks: List[Dict[str, Any]], max_additional_chunks: int = 15
) -> List[Dict[str, Any]]:
    if not self.graph:
        return seed_chunks

    community_ids = set()
    for chunk in seed_chunks:
        chunk_id = str(chunk.get("id"))
        node_id = self.chunk_to_node.get(chunk_id) or (chunk_id if chunk_id in self.graph else None)

        # Token Efficiency Check: Prune high-degree God Nodes from expansion paths
        if node_id and node_id in self.graph and node_id not in getattr(self, "god_nodes", set()):
            community = self.graph.nodes[node_id].get("community")
            if community is not None:
                community_ids.add(community)

    expanded_ids = set()
    for node_id, data in self.graph.nodes(data=True):
        # Exclude God Nodes from community retrieval pools
        if node_id in getattr(self, "god_nodes", set()):
            continue
        if data.get("community") in community_ids:
            expanded_ids.add(str(node_id))

    final_results = list(seed_chunks)
    added_count = 0

    # Expand context up to the strict community budgeting limit
    for chunk_id in expanded_ids:
        if added_count >= max_additional_chunks:
            break
        # Retrieve context chunk from database map and append
        # ...
```

---

## 4. Multi-Vendor Constraint Coordination

* **File**: [src/rag/multi_vendor_coordinator.py](file:///home/aryan/Projects/RAG-NetTwin/src/rag/multi_vendor_coordinator.py)

Forces global network peer alignments (e.g., OSPF hello timer parameters) before LLM configuration generation.

```python
# Extract from multi_vendor_coordinator.py
class MultiVendorCoordinator:
    def __init__(self):
        self.interop_map = {
            "ospf": ["area", "process_id", "hello_interval", "dead_interval", "wildcard_mask"],
            "bgp": ["local_as", "remote_as", "peer_group", "hold_time"],
            "vlan": ["vlan_id", "vlan_name"],
            "interface": ["mtu", "speed", "duplex", "subnet_mask"],
        }

    def extract_shared_constraints(self, intent: Any) -> List[InteroperabilityConstraint]:
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
        return constraints

    def build_coordination_prompt(
        self, constraints: List[InteroperabilityConstraint], master_plan: Optional[NetworkMasterPlan] = None
    ) -> str:
        prompt = ""
        if constraints:
            prompt += "\n### SHARED PARAMETER CONSTRAINTS ###\n"
            for c in constraints:
                prompt += f"- {c.protocol.upper()} {c.parameter_name}: {c.value}\n"
        if master_plan:
            prompt += "\n### GLOBAL NETWORK MASTER PLAN ###\n"
            prompt += "You MUST follow these assignments to ensure peer adjacencies form correctly:\n"
            prompt += json.dumps(master_plan.proposed_parameters, indent=2) + "\n"
        return prompt
```

---

## 5. Syntactic Normalization (Post-Processing)

* **File**: [src/rag/parameter_normalizer.py](file:///home/aryan/Projects/RAG-NetTwin/src/rag/parameter_normalizer.py)

Normalizes configurations to clean syntax errors before pushing them to Batfish or hardware console tests.

```python
# Extract from parameter_normalizer.py: post_process_config()
@staticmethod
def post_process_config(config: str, vendor: str) -> str:
    vendor = (vendor or "cisco").lower()
    if vendor != "cisco":
        return config

    processed = config

    # 1. Dynamic CIDR-to-mask conversion using ipaddress library
    def replace_cidr(match):
        prefix_cmd = match.group(1)  # e.g., "ip route" or "ipv6 route"
        ip = match.group(2)
        prefix = match.group(3)
        try:
            # Dynamic subnet mask calculation using ipaddress library
            net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
            if net.version == 6:
                return f"{prefix_cmd} {ip}/{prefix}"
            else:
                return f"{prefix_cmd} {ip} {net.netmask}"
        except Exception:
            if ":" in ip:
                return f"{prefix_cmd} {ip}/{prefix}"
            return f"{prefix_cmd} {ip} 255.255.255.0"

    processed = re.sub(
        r"\b((?:ip|ipv6) route\s+([0-9a-fA-F.:]+))/(\d+)",
        replace_cidr,
        processed,
        flags=re.IGNORECASE,
    )

    # 2. Map interface shorthand to IOU-compatible naming (Gigabit -> Ethernet)
    interface_maps = {
        r"GigabitEthernet": r"Ethernet",
        r"Gig": r"Ethernet",
        r"Gi": r"Ethernet",
        r"FastEthernet": r"Ethernet",
        r"TenGigabitEthernet": r"Ethernet",
        r"Ten": r"Ethernet",
        r"Te": r"Ethernet",
    }
    for short, full in interface_maps.items():
        processed = re.sub(rf"\b{short}(\s*\d+(?:/\d+)*)", rf"{full}\1", processed, flags=re.IGNORECASE)

    # 3. Convert three-tier interfaces (e.g. Ethernet1/0/24) to two-tier (Ethernet0/0)
    def map_three_tier_interface(match):
        full_name = match.group(1)
        port = int(match.group(4))
        mapped_port = port % 4
        return f"{full_name}0/{mapped_port}"

    processed = re.sub(
        r"\b(Ethernet)(\d+)/(\d+)/(\d+)\b",
        map_three_tier_interface,
        processed,
        flags=re.IGNORECASE,
    )

    return processed
```

---

## 6. Static Analysis & Verification

### 6.1 Batfish Validator
* **File**: [src/validation/batfish_validator.py](file:///home/aryan/Projects/RAG-NetTwin/src/validation/batfish_validator.py)

Passes configurations into a Docker-based Batfish session to parse commands and identify undefined configuration references.

```python
# Extract from batfish_validator.py: validate()
def validate(self, configs: Dict[str, str], intent: Any = None) -> Dict[str, Any]:
    # Thread-safe Pybatfish session initialization
    session = Session(host=self.host)
    unique_id = str(uuid.uuid4())[:8]
    network_name = f"rag_net_{unique_id}"
    snapshot_name = f"snapshot_{unique_id}"

    # Clean prose elements from raw config
    cleaned_configs = {dev: clean_cli_prose(cfg) for dev, cfg in configs.items()}

    # Create temporary directory for snapshot injection
    temp_dir = tempfile.mkdtemp()
    try:
        config_dir = Path(temp_dir) / "configs"
        config_dir.mkdir(parents=True)

        for host, text in cleaned_configs.items():
            # Force Juniper or Cisco extension based on syntax headers
            is_juniper = "set protocols" in text.lower() or "{" in text
            ext = ".conf" if is_juniper else ".cfg"
            with open(config_dir / f"{host}{ext}", "w") as f:
                f.write(text)

        session.set_network(network_name)
        session.init_snapshot(temp_dir, name=snapshot_name, overwrite=True)

        # Run Batfish syntax analysis
        issues = []
        parse_status = session.q.initIssues().answer().frame()
        if not parse_status.empty:
            for _, row in parse_status.iterrows():
                details = str(row.get("Details", ""))
                # Filter out known Batfish gaps to avoid false positives
                if any(gap.lower() in details.lower() for gap in self.known_gaps):
                    continue
                issues.append({"type": "PARSE_ISSUE", "details": details})

        # Run undefined references check
        undefined = session.q.undefinedReferences().answer().frame()
        if not undefined.empty:
            for _, row in undefined.iterrows():
                issues.append({
                    "type": "UNDEFINED_REFERENCE",
                    "details": f"{row.get('Structure_Type')} '{row.get('Structure_Name')}' is missing."
                })

        status = "PASS" if not issues else "FAIL"
        return {"status": status, "tier": 1, "issues": issues}
    finally:
        shutil.rmtree(temp_dir)
        session.delete_network(network_name)
```

---

## 7. Hallucination Detection Audits

* **File**: [src/evaluation/hallucination_detector.py](file:///home/aryan/Projects/RAG-NetTwin/src/evaluation/hallucination_detector.py)

Audits configurations for placeholder matching, invalid citations, ungrounded CLI commands, and unauthorized parameters.

```python
# Extract from hallucination_detector.py: detect()
class HallucinationDetector:
    HALLUCINATION_PATTERNS = [
        r"<YOUR_[A-Z_]+>",
        r"<ENTER_[A-Z_]+>",
        r"PLACEHOLDER",
        r"dummy-config",
        r"\bUnknown\b",
        r"\bTBD\b",
    ]

    def detect(
        self,
        config: str,
        citations: List[str],
        valid_source_ids: List[str],
        retrieved_texts: Optional[List[str]] = None,
        intent_context: str = "",
        intent_params: Optional[Dict[str, Any]] = None,
        master_plan: Optional[Dict[str, Any]] = None,
        authorized_citations: Optional[List[str]] = None,
    ) -> HallucinationReport:
        suspicious = []
        invalid_cites = []

        # 1. Placeholder Matching
        config_clean = re.sub(r"\[Ref: [^\]]+\]", "", config)
        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, config_clean)
            if matches:
                suspicious.extend(list(set(matches)))

        # 2. Citation Verification
        full_authorized = set(valid_source_ids + (authorized_citations or []))
        full_authorized.add("BASE_CLI_KNOWLEDGE")
        for cite in citations:
            clean_cite = cite.replace("ID:", "").strip()
            if clean_cite not in full_authorized:
                invalid_cites.append(cite)

        # 3. Grounding Verification
        ungrounded = []
        if retrieved_texts or intent_context:
            ungrounded = self._check_command_grounding(config_clean, retrieved_texts or [], intent_context)

        # 4. Parameter Binding Verification
        unauthorized = []
        if intent_params or master_plan or retrieved_texts:
            unauthorized = self._check_parameter_binding(
                config_clean,
                intent_params or {},
                master_plan or {},
                grounding_context=retrieved_texts,
            )

        is_hallucinated = len(suspicious) > 0 or len(invalid_cites) > 0 or len(ungrounded) > 0 or len(unauthorized) > 0
        return HallucinationReport(
            is_hallucinated=is_hallucinated,
            suspicious_commands=suspicious,
            invalid_citations=invalid_cites,
            ungrounded_commands=ungrounded,
            unauthorized_parameters=unauthorized
        )
```

---

## 8. Multi-Tier Gating & Evaluation Orchestration

* **File**: [run_paper_eval.py](file:///home/aryan/Projects/RAG-NetTwin/run_paper_eval.py)

Orchestrates the evaluation pipeline by verifying configurations through the Batfish linter first, then deciding whether to skip the GNS3 emulation sandbox depending on the `--evaluation-mode` flag settings.

```python
# Extract from run_paper_eval.py: evaluate_intent()
# Determines GNS3 bypass / short-circuiting logic

# 1. Check Batfish status
batfish_failed = val_report.get("status") in ["ERROR", "FAIL", "REJECT_FOR_MANUAL_REVIEW"]
should_run_gns3 = bool(self.run_gns3 and self.gns3)

# 2. Early short-circuiting in strict mode
if should_run_gns3 and batfish_failed and self.evaluation_mode == "strict":
    logger.warning(
        f"Short-circuiting GNS3 validation due to Batfish failure in strict mode ({val_report.get('status')})."
    )
    functional_status = "SKIPPED_FAIL"
    functional_errors = ["Skipped GNS3 validation due to Batfish failure in strict mode."]
    should_run_gns3 = False

# 3. Proceed to GNS3 emulation sandbox if allowed and connected
if should_run_gns3 and self.gns3 is not None:
    try:
        with self.gns3_lock:
            g_res = self.gns3.validate(device_configs, intent)
            gns3_car = g_res.get("car", 0.0)
            is_multi_vendor = g_res.get("is_multi_vendor", False)
            # ... deploy virtual nodes and push configs ...
```

---

## 9. Transparent API Key Rotation (Groq Rate Limits)

* **File**: [src/llm/provider.py](file:///home/aryan/Projects/RAG-NetTwin/src/llm/provider.py)

During large-scale paper evaluation runs, standard free/tier-1 developer limits on LLM endpoints are easily saturated (returning HTTP 429). RAG-NetTwin implements a thread-safe proxy/wrapper layer that dynamically shifts to alternative keys when a limit is reached.

```python
# Extract from provider.py: GroqKeyRotator, RotatingChatGroq, and RotatingRunnable

class GroqKeyRotator:
    """Manages rotation of Groq API keys when rate limits are hit (thread-safe)."""
    def __init__(self):
        self._keys: List[str] = []
        self._current_index = 0
        self._lock = threading.Lock()
        # Loads comma-separated strings from GROQ_API_KEYS or GROQ_API_KEY envs

    def rotate_key(self) -> bool:
        with self._lock:
            if len(self._keys) <= 1:
                return False
            self._current_index = (self._current_index + 1) % len(self._keys)
            return True

class RotatingChatGroq(BaseChatModel):
    """ChatGroq wrapper that supports dynamic key rotation on rate limits."""
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        attempts = max(1, self.rotator.get_keys_count())
        for attempt in range(attempts):
            try:
                return self.client._generate(messages, stop, run_manager, **kwargs)
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "rate limit" in err_str.lower()) and attempt < attempts - 1:
                    if self.rotator.rotate_key():
                        self._rebuild_client()
                        continue
                raise e

class RotatingRunnable(Runnable):
    """Wraps a structured runnable to dynamically rebuild and retry with rotated keys on 429 errors."""
    # Wraps langchain runnables (e.g. structured_llm) to recreate and retry them
    # on rate limit errors with rotated keys.
```

