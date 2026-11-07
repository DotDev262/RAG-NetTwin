# RAG-NetTwin v2 User Guide & Architectural Reference

This guide details how to use **RAG-NetTwin v2**, with specific instructions for:
1. **Interactive CLI & Synthesis Pipeline** (with State-Invariant Graph Controller)
2. **Multi-Tier Validation Pipeline** (Batfish Tier 1 + Topology-Aware Tier 1.5)
3. **Compile-Time Rule Encoder** (`src.rule_encoder`) for extracting alignment rules from RFCs and vendor specs
4. **Offline GNS3 Policy & Batfish WSL Configuration**
5. **Running Paper Evaluations & Benchmarks**

---

## Table of Contents

- [1. Architecture Overview](#1-architecture-overview)
- [2. Environment & Prerequisites](#2-environment--prerequisites)
- [3. Running the Interactive CLI](#3-running-the-interactive-cli)
- [4. State-Invariant Graph Controller (Module 1)](#4-state-invariant-graph-controller-module-1)
- [5. Topology-Aware Validation Pipeline (Module 2)](#5-topology-aware-validation-pipeline-module-2)
- [6. Compile-Time LLM Rule Encoder (Offline Pipeline)](#6-compile-time-llm-rule-encoder-offline-pipeline)
- [7. Testing Environment & Batfish via WSL](#7-testing-environment--batfish-via-wsl)
- [8. Running Evaluations & Automated Test Suites](#8-running-evaluations--automated-test-suites)

---

## 1. Architecture Overview

```
 [Natural Language Intent]
            │
            ▼
┌───────────────────────────────────────────────┐
│              Intent Parser                    │
│    (StructuredIntent, Devices, Protocols)     │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│     State-Invariant Graph Controller (v2)     │
│   • Global NetworkX Topology Graph Registry   │
│   • Innate State Invariant Prompt Injection   │
│   • Interactive Conflict Interception Loop    │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│         Structured LLM Synthesizer            │
│   • Grounded Documentation Retrieval (RAG)    │
│   • Version-locked CLI Generation             │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│      Tier 1: Batfish Static Verification      │
│   • Syntax Parsing & Reference Resolution     │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│  Tier 1.5: Topology-Aware Validation Pipeline │
│   • Cross-Device Adjacency Verification       │
│   • OSPF Area / Hello / Dead / MTU Checks     │
│   • BGP remote-as & Password Reciprocity      │
│   • Subnet Continuity & ACL Direction Logic   │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│       Verified Multi-Device Configurations    │
└───────────────────────────────────────────────┘
```

---

## 2. Environment & Prerequisites

- **Python**: Python 3.10+ (using `uv`)
- **Network Validation**: Batfish running via Docker or inside WSL:
  ```bash
  docker run --name batfish -v batfish-data:/data -p 8888:8888 -p 9997:9997 -p 9996:9996 batfish/allinone
  ```
- **Environment Variables**: Create or update `.env`:
  ```ini
  GROQ_API_KEY=your_groq_api_key
  BATFISH_HOST=127.0.0.1
  BATFISH_PORT=9996
  ```

---

## 3. Running the Interactive CLI

Launch the main pipeline:
```powershell
uv run python main.py
```

### Example Multi-Router Intent:
```
Configure OSPF Area 0 on Router-A (cisco) and Router-B (juniper) with shared link 10.0.0.0/30, hello-interval 5, and dead-interval 20.
```

### What Happens Behind the Scenes:
1. **[1/3] Parsing Intent**: Generates structured parameters and devices.
2. **[2/3] State-Invariant Injection**: The Graph Controller models connecting links and injects mandatory parameter constraints into the LLM prompt.
3. **[3/3] Configuration Generation**: Commands are synthesized with direct documentation citations.
4. **[4/4] Tier 1 Validation (Batfish)**: Static syntax and AST parsing verify device CLI grammar.
5. **[4.5/6] Tier 1.5 Topology-Aware Validation**: Cross-checks mutual OSPF area, timers, and subnet alignment across Router-A and Router-B.

---

## 4. State-Invariant Graph Controller (Module 1)

Located in [`src/rag/state_graph_controller.py`](file:///C:/Users/Aryan/Projects/RAG-NetTwin/src/rag/state_graph_controller.py).

### Key Functions
- **Topology Graph Creation**: Models multi-vendor nodes and connecting links in `networkx.Graph`.
- **Innate Constraint Injection**: Prior to synthesizing commands, injects fixed parameters into the prompt:
  - Matching OSPF Area IDs (Area 0 vs Area 0.0.0.0)
  - Identical Hello/Dead timers
  - Identical MD5 message-digest authentication keys
  - Shared link IP subnets (e.g. `10.0.0.1/30` <-> `10.0.0.2/30`)
  - Reciprocal BGP AS numbers and peer IPs
- **Interactive Interception**:
  If adjacent node configurations diverge, the controller intercepts the output, flags the semantic conflict, and prompts the LLM to self-correct before passing the configuration forward.

---

## 5. Topology-Aware Validation Pipeline (Module 2)

Located in [`src/validation/topology_validator.py`](file:///C:/Users/Aryan/Projects/RAG-NetTwin/src/validation/topology_validator.py).

### How to Use Programmatically
```python
from src.validation.topology_validator import TopologyAwareValidator
from src.schemas.intent import StructuredIntent

validator = TopologyAwareValidator()

configs = {
    "Router-A": """
        interface GigabitEthernet0/1
         ip address 10.0.0.1 255.255.255.252
         ip ospf 1 area 0
         ip ospf hello-interval 5
    """,
    "Router-B": """
        set interfaces ethernet eth0 address 10.0.0.2/30
        set protocols ospf area 0 interface eth0
        set protocols ospf area 0 hello-interval 5
    """
}

report = validator.validate(configs)
print("Status:", report["status"])  # PASS, FAIL, or WARNING
```

### Semantic Error Codes Emitted
| Error Code | Description |
|---|---|
| `OSPF_AREA_MISMATCH` | Connected router interfaces belong to different OSPF areas |
| `OSPF_TIMER_MISMATCH` | Hello or Dead timer discrepancy between adjacent peers |
| `OSPF_MTU_MISMATCH` | MTU mismatch preventing OSPF adjacency full state |
| `OSPF_AUTH_MISMATCH` | Missing or mismatched MD5 message-digest keys |
| `BGP_REMOTE_AS_MISMATCH` | BGP neighbor remote-as does not match adjacent local ASN |
| `BGP_AUTH_MISMATCH` | BGP peer MD5 authentication password mismatch |
| `SUBNET_MISMATCH` | Connected interface IPs do not belong to the same IP subnet |
| `ACL_DIRECTION_ERROR` | Inbound filtering applied outbound or vice versa |

---

## 6. Compile-Time LLM Rule Encoder (Offline Pipeline)

Located in [`src/rule_encoder/`](file:///C:/Users/Aryan/Projects/RAG-NetTwin/src/rule_encoder).

The Rule Encoder runs **offline/compile-time** to parse RFC specifications and vendor CLI guides into structured alignment rules without runtime overhead.

### Command Line Interface
```powershell
uv run python -m src.rule_encoder.cli \
    --source data/graph_corpus/ \
    --vendor-pair cisco,juniper \
    --output config/alignment_rules_registry.json
```

### CLI Arguments
| Flag | Description | Default |
|---|---|---|
| `--source`, `-s` | Path to text, RFC, HTML, or PDF document(s) | *Required* |
| `--vendor-pair`, `-v` | Comma-separated target vendors | `cisco,juniper` |
| `--output`, `-o` | Output file for compiled rule registry | `config/alignment_rules_registry.json` |
| `--model`, `-m` | LLM model identifier | Default system LLM |
| `--dry-run` | Inspect extracted rules without writing to disk | `False` |

### Runtime Consumption
The compiled `config/alignment_rules_registry.json` is automatically loaded by `StateInvariantGraphController` at initialization to enforce standards-compliant invariants across all multi-router syntheses.

---

## 7. Testing Environment & Batfish via WSL

> [!IMPORTANT]
> **GNS3 Offline Policy**:
> GNS3 emulation is currently offline/disabled. Do **not** attempt to run GNS3 emulators during development. All validation testing must be strictly confined to **Batfish via WSL** or local static evaluation.

### Checking Batfish Status
Run this quick diagnostic to confirm your Batfish container in WSL is accessible:
```powershell
$env:PYTHONUTF8="1"
$env:GROQ_API_KEY="dummy_key_for_testing"
uv run python -c "from src.validation.batfish_validator import BatfishValidator; v = BatfishValidator(); print('Batfish Connected:', v.session is not None)"
```

---

## 8. Running Evaluations & Automated Test Suites

### Running Unit Tests
```powershell
$env:PYTHONUTF8="1"
$env:GROQ_API_KEY="dummy_key_for_testing"

# Run Rule Encoder tests
uv run pytest tests/test_rule_encoder.py -v

# Run Topology Validator and Graph Controller tests
uv run pytest tests/test_topology_and_graph_controller.py -v

# Run Parameter Normalization regression tests
uv run pytest tests/test_parameter_normalizer.py -v
```

### Running Paper Evaluation (Batfish Only)
```powershell
uv run python run_paper_eval.py --evaluation-mode strict --retrieval-mode tiered
```
*(Notice `--run-gns3` is omitted to preserve the GNS3 offline constraint).*
