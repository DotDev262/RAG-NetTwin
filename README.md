# Version-Aware RAG for Reliable Network CLI Configuration Synthesis

A research system that generates network configurations from natural language intents while minimizing LLM hallucinations through RAG and multi-tier validation.

**Target**: <2% hallucination rate (current: **0%**)

---

## 🎯 What It Does

```
User Intent          RAG-NetTwin              Validated Config
─────────────────>  ────────────────>  ──────────────────────
"Configure OSPF      Generate CLI with        Batfish validates
on Cisco 17.6"      citations from docs       Syntax + Semantics
```

## ✨ Key Features

- **RAG-Augmented Generation**: Commands grounded in official Cisco/Juniper documentation
- **Version-Locked Retrieval**: Filters by OS version (e.g., IOS-XE 17.6, JunOS 21.4)
- **Citation Tracking**: Every command includes source reference
- **Tier 1 Validation**: Batfish static analysis for syntax validation
- **Multi-Vendor Support**: Cisco IOS-XE and Juniper JunOS
- **Tier-based Chunking**: Hierarchical chunks (Tier 1: CLI, Tier 2: Context, Tier 3: Examples)

## 📊 Results

| Metric | Vanilla LLM | RAG-NetTwin | Improvement |
|--------|-------------|-------------|-------------|
| Syntactic Validity | 52.2% | **87.0%** | +35% |
| Hallucination Rate | 4.3% | **0.0%** | Target: <2% |
| CFR Faithfulness | 91.3% | 82.6% | (trade-off) |

**Full evaluation**: 23 test intents with Batfish validation

### Performance Metrics

| Metric | Value |
|--------|-------|
| Average Latency | ~20 seconds |
| Syntactic Validity | 87.0% |
| Hallucination Rate | 0.0% |
| Batfish Validation | ~400ms per intent |
| Knowledge Base Size | 10,333 chunks |
| Groq API (free tier) | 1M tokens/day |

---

## ⚠️ Known Limitations

| Limitation | Current | Target | Notes |
|------------|---------|--------|-------|
| Syntactic Validity | 87.0% | 98.8% | Multi-vendor edge cases |
| CFR Faithfulness | 82.6% | 97.2% | Trade-off for zero hallucination |
| Knowledge Base | 10,333 chunks | 50,000+ | Limited vendor documentation |
| Validation Tier | Tier 1 only | Tier 1-3 | Batfish only, no Containerlab/GNS3 |

**Notes:**
- CFR (Command Faithfulness Rate) measures how well generated configs match intent parameters
- Paper targets assume 50,000+ pages of vendor docs; current KB has ~7,000 pages
- Multi-device intents sometimes split incorrectly

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/your-repo/RAG-NetTwin.git
cd RAG-NetTwin

# Setup virtual environment
uv sync

# Configure API key (add to .env)
# GROQ_API_KEY=your_key_here

# Run evaluation
uv run python run_paper_eval.py
```

**Requirements:**
- Python 3.10+
- Groq API key (free tier: 1M tokens/day)
- Docker (for Batfish validation)

---

## 📁 Project Structure

```
RAG-NetTwin/
├── run_paper_eval.py      # Main evaluation script
├── main.py                 # CLI entry point
├── src/
│   ├── parser/             # Intent parsing (NLP → Structured)
│   ├── rag/                # Config generation + Vector store
│   ├── validation/         # Batfish/Tier validators
│   └── evaluation/         # Hallucination detection
├── docs/
│   ├── PAPER.md            # Journal paper draft
│   └── research/           # Research plan
└── scripts/
    └── quick_eval.py       # Quick testing (no Batfish)
```

---

## 🔧 Running Tests

```bash
# Quick test (no Batfish, ~5s)
uv run python scripts/quick_eval.py

# Full evaluation (with Batfish, ~10 min)
uv run python run_paper_eval.py

# With vanilla LLM comparison
uv run python run_paper_eval.py --run-vanilla
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `AGENTS.md` | Project context and current status |
| `docs/PAPER.md` | Journal paper draft |
| `docs/QUICKSTART.md` | Setup guide |
| `docs/ARCHITECTURE.md` | System architecture |

---

## 🎓 For Faculty/Examiners

**Innovation**: OS version-locked RAG that retrieves commands specific to the target device's OS version, eliminating cross-version command pollution.

**Validation**: Tier 1 static analysis using Batfish catches syntactic errors before deployment.

**Research Output**:
- 10,333+ documentation chunks in knowledge base (Tier 1: 334, Tier 2: 9,760, Tier 3: 1)
- 0% hallucination rate on 23 test intents
- +35% syntactic validity over vanilla LLM

---

## 💾 Knowledge Base (ChromaDB)

**Total Chunks**: 10,333

### Schema (Metadata Fields)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `vendor` | string | Network vendor | `cisco`, `juniper` |
| `os_version` | string | OS version for version-locking | `17.6`, `21.4` |
| `tier` | int | Chunk tier (1=CLI, 2=Context, 3=Example) | `1`, `2`, `3` |
| `command_hierarchy` | JSON | CLI hierarchy path | `["router", "bgp", "neighbor"]` |
| `context_tags` | JSON | Feature tags | `["routing", "bgp", "peer"]` |
| `source_file` | string | Source PDF | `junos-bgp-config.pdf` |
| `page_range` | JSON | PDF page range | `[10, 15]` |

### Version-Locked Retrieval Example

```python
# Query built from parsed intent
# Intent: "Configure OSPF area 0 on router1 (Cisco 17.6)"
query = "ospf create area network router"  # protocol + action + parameters

# Retrieve with version locking
results = vector_store.retrieve(
    query=query,
    vendor="cisco",
    os_version="17.6",
    n_results=5
)

# Fallback chain: vendor+version → vendor only → unfiltered
```

**Query Construction** (from `src/rag/config_generator.py:176-179`):
```python
query = (
    f"{structured_intent.protocol} {structured_intent.action} "
    + " ".join(structured_intent.parameters.keys())
)
```

### Tier Distribution

| Tier | Count | Description |
|------|-------|-------------|
| Tier 1 | 334 | CLI commands (exact syntax) |
| Tier 2 | 9,760 | Context and parameters |
| Tier 3 | 1 | Examples and use cases |
| None | 238 | Uncategorized |

### Vendor Distribution

| Vendor | Chunks | Percentage |
|--------|--------|------------|
| Juniper (JunOS) | 6,483 | 63% |
| Cisco (IOS-XE) | 3,850 | 37% |

### OS Version Coverage

| Version | Chunks |
|---------|--------|
| JunOS 21.4 | 6,000+ |
| IOS-XE 17.6 | 2,300+ |
| IOS-XE 17.14 | 475 |
| IOS-XE 17.15 | 276 |
| IOS-XE 17.16 | 237 |
| IOS-XE 16.9 | 188 |

---

## 🔬 Examples

### 1. Intent Parsing

**Input:**
```
"Configure OSPF area 0 on router1 (Cisco 17.6)"
```

**Parsed StructuredIntent:**
```python
{
    "protocol": "OSPF",
    "action": "create",
    "devices": [{"name": "router1", "vendor": "cisco", "os_version": "17.6"}],
    "parameters": {"area": "0"},
    "original_text": "Configure OSPF area 0 on router1 (Cisco 17.6)"
}
```

### 2. Generated Config with Citations

**Output:**
```cisco
router ospf 1
 network 10.0.0.0 0.0.0.255 area 0
!
! [Source: ios-xe-ospf-config-guide-17.6.pdf, pages 10-15]
```

### 3. Full Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ "Configure OSPF on Cisco 17.6"                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ IntentParser.parse()                                           │
│ → StructuredIntent(protocol="OSPF", vendor="cisco",            │
│                    os_version="17.6", parameters={area: 0})     │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ConfigGenerator.generate() with version-locked RAG             │
│ → VectorStore.retrieve(vendor="cisco", os_version="17.6")      │
│ → LLM generates CLI with citations                             │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ HallucinationDetector.check()                                  │
│ → Verifies every command has matching citation                 │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ BatfishValidator.validate() [optional]                         │
│ → Static analysis catches remaining errors                     │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Final CLI Output with citations                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Test Intent Examples

| Intent | Vendor | Protocol |
|--------|--------|----------|
| "Configure OSPF area 0 on interface GigabitEthernet0/1 with network 10.0.0.0/24" | Cisco | OSPF |
| "Create an ACL named BLOCK_SSH that denies TCP traffic from 192.168.1.0/24 to any port 22" | Cisco | ACL |
| "Set up BGP AS 65001 and peer with 10.1.1.1" | Cisco | BGP |
| "On Juniper MX router, configure BGP peer 10.1.1.2 with autonomous system 65001" | Juniper | BGP |
| "Configure OSPF area 0 between Cisco and Juniper on their shared link" | Multi | OSPF |

---

## ⚙️ Tech Stack

- **LLM**: Llama 3.1/3.3 via Groq API
- **Vector DB**: ChromaDB (local)
- **Embeddings**: intfloat/e5-small-v2
- **Validation**: Batfish (Docker)
- **Language**: Python 3.10+

---

## 📄 License

MIT License - See LICENSE file

---
**Current Status:** Phase 2 Research Platform Implementation Complete ✅
