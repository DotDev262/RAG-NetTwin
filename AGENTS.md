# AGENTS.md - Project Context for RAG-NetTwin

**Project Name**: Hallucination-Mitigated Intent-Based Networking (RAG-NetTwin)  
**Type**: B.Tech Final Year Project with Journal Publication Goal  
**Timeline**: 10 Months (5 months implementation + 5 months paper)  
**Last Updated**: May 23, 2026  

---

## 🎯 PROJECT OVERVIEW

**Objective**: Build a system that generates network configurations from natural language intents while minimizing LLM hallucinations through RAG + multi-tier validation.

**Key Innovation**: OS Version-Locked RAG with **Zero-Tolerance Hallucination Refinement**, Three-Tier Validation, and Hierarchical Graph-Augmented Retrieval.  
**Target**: <2% hallucination rate (Current: 0.0% with zero-tolerance loop)

**Core Components**:
1. **Hierarchical GraphRAG**: Uses a knowledge graph to expand context from syntax seeds to hierarchical parents and siblings.
2. **Multi-Query Expansion**: 3x retrieval recall boost via semantic query variations.
3. **Network Master Plan**: Architect-level pre-planning for shared topology parameters (IPs, ASNs, IDs) and logical `deployment_sequence`.
4. **Citation Gating**: Mandatory `source_id` binding for every generated command block.
5. **Three-Tier Validation**: Batfish (Static), Containerlab (Emulation), and GNS3 (Simulation).

---

## 📋 CURRENT STATUS

**Phase**: Final Paper Drafting & Evaluation Hardening  
**Last Updated**: May 23, 2026

**Recent Milestones**:
- ✅ **Zero-Tolerance Hallucination Loop**: Integrated real-time auditing and refinement into the generation cycle.
- ✅ **Multi-Vendor Digital Twin**: Hardened GNS3 support for Juniper Junos with vendor-specific navigation.
- ✅ **Syntactic Post-Processing**: Automated CIDR-to-Mask conversion for Cisco static routes.
- ✅ **Codebase Release-Ready**: Organized repository into dedicated `benchmarks/`, `notebooks/`, and `paper-analysis/` for publication.
- ✅ **16.4x Token Reduction**: Achieved massive efficiency gain via God Node pruning and community budgeting.
- ✅ **Dynamic Few-Shot Gating**: Implemented confidence-based gating (0, 1, or 2 examples) based on pilot search distance.
- ✅ **Knowledge Graph Finalized**: Constructed 1334-node graphify KG across 162 functional communities.
- ✅ **System Hardening & Evaluation Hardening**: Successfully achieved 100% GNS3 hardware acceptance, 100% Batfish validation success (Strict SV), and 0% hallucination rate on all N=35 paper intents.

**Next Action**: Draft and finalize the journal paper with the newly verified zero-hallucination results.

---

## 🔧 KEY ARCHITECTURAL DECISIONS

### 1. **Modular "Source-of-Truth" Architecture**
- All data models isolated in `src/schemas/` (e.g., `StructuredIntent`, `DeviceIntent`).
- Validation logic split into `src/validation/` (Batfish, Containerlab, GNS3) and `src/evaluation/` (HallucinationDetector).

### 2. **"Strict Grounding" Policy**
- **Incompleteness over Fabrication**: Instruct model to omit commands rather than invent syntax.
- **Citation Gating**: Every generated block must map back to a verified `source_file` in the KG.
- **Refinement Gating**: REJECT_FOR_MANUAL_REVIEW (parsing issues) now triggers the LLM refinement loop.

### 3. **Graph-Driven Token Efficiency**
- **God Node Pruning**: Filter high-degree hubs (e.g., `VectorStore`) to prevent context explosion.
- **Community Budgeting**: Strict limit of 15 additional chunks per community expansion.
- **Adaptive Thresholding**: Pilot search distance > 0.55 triggers Multi-Query; otherwise, direct match is used.
- **Lite-Path Heuristic**: Zero-RAG path for common administrative/boilerplate CLI tasks.

### 4. **Fail-Fast Configuration**
- Uses `pydantic-settings` to validate environment variables and API keys immediately at startup.

---

## 🏗️ TECH STACK

### **Core**:
- **Vector DB**: ChromaDB (local)
- **Knowledge Graph**: networkx (via `graphify`)
- **LLM**: Gemini 2.0 Flash (primary) & Llama 3.3 70B
- **Static Analysis**: Mypy
- **Linter/Formatter**: Ruff

### **Research Tools**:
- **Tier 1**: Batfish (Static Verification)
- **Tier 2**: Containerlab (Lightweight Emulation)
- **Tier 3**: GNS3 (Functional Simulation)
- **Tracing**: Structured JSON traces in `results/traces/`

---

## 📁 PROJECT STRUCTURE

```
RAG-NetTwin/
├── benchmarks/         # Performance comparison scripts
├── notebooks/          # Google Colab reproduction notebooks
├── paper-analysis/     # Scripts for generating paper figures/tables
├── src/
│   ├── schemas/           # Pydantic models (Intent, Device, etc.)
│   ├── rag/               # VectorStore, QueryExpander, Normalizer, Coordinator
│   ├── parser/            # IntentParser, InventoryResolver
│   ├── validation/        # Batfish, Containerlab, GNS3, ReferentialIntegrity
│   ├── evaluation/        # CacheManager, StatsReporter, HallucinationDetector
│   ├── exporter/          # GNS3Exporter
│   └── utils/             # Modularized helpers (logger, text, system, metrics)
├── ui/
│   ├── frontend/          # index.html (Visual Grounding Dashboard)
│   └── backend/           # FastAPI app.py
├── scripts/               # Essential setup and seeding scripts
├── graphify-out/          # Knowledge Graph assets (1334 nodes, 162 communities)
└── devenv.nix             # Nix-based environment config
```

---

## 📊 EVALUATION RESULTS (May 2026)

### Phase 1 Research Evaluation Summary (N=35 intents)

| Mode | Strict SV | PEA (Parameter) | GNS3 CAR | Hallucination |
|------|-----------|-----------------|----------|---------------|
| Vanilla LLM | 74.3% | 80.0% | 0.0% | 25.7% |
| **RAG-NetTwin (Tiered)** | **100.0%** | **97.1%** | **100.0%** | **0.0%** |

*Note: Strict SV reflects Batfish "PASS/WARNING". GNS3 CAR reflects hardware command acceptance. The zero-tolerance hallucination refinement and syntax-mapping loops achieve a perfect CAR/SV and 0% hallucinations.*

### Retrieval Benchmarks (GraphRAG vs Baseline)

| Metric | Baseline | Advanced RAG | Improvement |
| :--- | :--- | :--- | :--- |
| Mean Semantic Precision | 0.2764 | **0.4856** | **+75.6%** |
| Total Recall (Unique Chunks) | 10 | **135** | **+1250%** |
| **Tokens Per Query** | **~57,533** | **~3,503** | **16.4x Reduction** |

---

## 💡 KEY RESEARCH INNOVATIONS

1. **OS Version-Locked Retrieval**: Ensuring syntax matches specific firmware via `InventoryResolver`.
2. **Zero-Tolerance Hallucination Refinement**: Multi-stage auditing that re-prompts the LLM upon detecting ungrounded params.
3. **Deterministic Syntactic Verification Gate**: Tier 1 validation before any execution attempt.
4. **Adaptive Community Anchoring**: Using KG community labels and budgeting to mitigate retrieval noise.
5. **Config Acceptance Rate (CAR)**: Quantitative measurement of hardware-level syntax acceptance.

---

## ⚙️ QUICK START

```bash
# 1. Enter the environment
devenv shell

# 2. Run the main evaluation (using optimized cache flags)
uv run python run_paper_eval.py --max-workers 1 --run-gns3

# 3. Run the retrieval benchmark
uv run python benchmarks/graph_retrieval_benchmark.py

# 4. Generate/Update Knowledge Graph
graphify update .

# 5. Start the UI
uv run python ui/backend/app.py
```

---

**End Goal**: Publish a high-impact paper demonstrating that **Structured Knowledge Graphs** combined with **Strict Citation Gating** can enable production-ready Intent-Based Networking with near-zero hallucinations.
