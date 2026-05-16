# Version-Aware RAG for Reliable Network CLI Configuration Synthesis

A research system that generates network configurations from natural language intents while minimizing LLM hallucinations through RAG and multi-tier validation.

**Current Baseline**: 8.6% hallucination rate (Target: <2%)

---

## 🎯 What It Does

```
User Intent          RAG-NetTwin              Validated Config
─────────────────>  ────────────────>  ──────────────────────
"Configure OSPF      Generate CLI with        Batfish validates
on Cisco 17.6"      citations from docs       Syntax + Semantics
```

## ✨ Key Features

- **RAG-Augmented Generation**: Commands grounded in official Cisco/Juniper documentation.
- **Zero-Tolerance Hallucination Loop**: Real-time auditing and refinement based on intent parameters.
- **Version-Locked Retrieval**: Filters by OS version (e.g., IOS-XE 17.6, JunOS 21.4).
- **Three-Tier Validation**:
    - **Tier 1**: Batfish static analysis for syntax validation.
    - **Tier 3**: GNS3 functional simulation for multi-vendor verification.
- **Multi-Vendor Support**: Cisco IOS-XE and Juniper JunOS.

## 📊 Results (N=35)

| Metric | Vanilla LLM | RAG-NetTwin | Improvement |
|--------|-------------|-------------|-------------|
| Syntactic Validity | 74.3% | **77.1%** | +2.8% |
| Parameter Accuracy (PEA) | 80.0% | **97.1%** | +17.1% |
| Hallucination Rate | 25.7% | **8.6%** | -17.1% |

**Full evaluation**: 35 test intents with Batfish and GNS3 validation.

### Performance Metrics

| Metric | Value |
|--------|-------|
| Average Latency | ~20 seconds |
| Syntactic Validity | 77.1% |
| Parameter Accuracy | 97.1% |
| Hallucination Rate | 8.6% |
| Token Reduction | **16.4x** (via GraphRAG) |

---

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/your-repo/RAG-NetTwin.git
cd RAG-NetTwin

# Setup environment with devenv
devenv shell

# Run evaluation
uv run python run_paper_eval.py --max-workers 1 --run-gns3
```

**Requirements:**
- Python 3.10+
- Groq API key
- Docker (for Batfish and GNS3)

---

## 📁 Project Structure

```
RAG-NetTwin/
├── benchmarks/         # Performance comparison scripts
├── notebooks/          # Reproduction notebooks
├── paper-analysis/     # Results analysis and plotting
├── src/
│   ├── parser/         # Intent parsing (NLP → Structured)
│   ├── rag/            # Config generation + Vector store
│   ├── validation/     # Batfish/GNS3 validators
│   └── evaluation/     # Hallucination detection
├── ui/                 # Visual Grounding Dashboard
└── run_paper_eval.py   # Main evaluation engine
```

---

## 🔧 Running Tests

```bash
# Core evaluation (with Batfish and GNS3)
uv run python run_paper_eval.py --run-gns3

# Retrieval benchmark
uv run python benchmarks/graph_retrieval_benchmark.py

# Regression tests
pytest tests/
```

---

## 📚 Documentation

| File | Description |
|------|-------------|
| `AGENTS.md` | Detailed project context and status |
| `docs/PAPER.md` | Journal paper draft |
| `docs/ARCHITECTURE.md` | System architecture |

---

## 💾 Knowledge Base (GraphRAG)

**Total Nodes**: 1,334

### Version-Locked Retrieval Example

```python
# Query built from parsed intent
# Intent: "Configure OSPF area 0 on router1 (Cisco 17.6)"
query = "ospf create area network router"

# Retrieve with version locking
results = vector_store.retrieve(
    query=query,
    vendor="cisco",
    os_version="17.6",
    n_results=5
)
```

---

## 📄 License

MIT License - See LICENSE file

---
**Current Status:** Evaluation Hardening Phase ✅
