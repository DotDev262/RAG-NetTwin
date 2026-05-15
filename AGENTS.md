# AGENTS.md - Project Context for RAG-NetTwin

**Project Name**: Hallucination-Mitigated Intent-Based Networking (RAG-NetTwin)  
**Type**: B.Tech Final Year Project with Journal Publication Goal  
**Timeline**: 10 Months (5 months implementation + 5 months paper)  
**Last Updated**: May 11, 2026  

---

## 🎯 PROJECT OVERVIEW

**Objective**: Build a system that generates network configurations from natural language intents while minimizing LLM hallucinations through RAG + multi-tier validation.

**Key Innovation**: OS Version-Locked RAG with Three-Tier Validation and Hierarchical Graph-Augmented Retrieval.  
**Target**: <2% hallucination rate (Current: 5.7% with strict gating)

**Core Components**:
1. **Hierarchical GraphRAG**: Uses a knowledge graph to expand context from syntax seeds to hierarchical parents and siblings.
2. **Multi-Query Expansion**: 3x retrieval recall boost via semantic query variations.
3. **Network Master Plan**: Architect-level pre-planning for shared topology parameters (IPs, ASNs, IDs) and logical `deployment_sequence`.
4. **Citation Gating**: Mandatory `source_id` binding for every generated command block.
5. **Three-Tier Validation**: Batfish (Static), Containerlab (Emulation), and GNS3 (Simulation).

---

## 📋 CURRENT STATUS

**Phase**: Final Paper Drafting & Graph-Driven Analysis  
**Last Updated**: May 11, 2026

**Recent Milestones**:
- ✅ **16.4x Token Reduction**: Achieved massive efficiency gain via God Node pruning and community budgeting.
- ✅ **Dynamic Few-Shot Gating**: Implemented confidence-based gating (0, 1, or 2 examples) based on pilot search distance.
- ✅ **Hardened Lite-RAG Path**: Expanded heuristic to bypass RAG for boilerplate tasks (NTP, Logging, Hostname, Interface Enable).
- ✅ **Knowledge Graph Finalized**: Constructed 863-node graphify KG across 189 functional communities.
- ✅ **Adaptive Retrieval**: Implemented distance-based expansion gating (threshold 0.55) to bypass expensive LLM steps.
- ✅ **Semantic Tagging**: Integrated KG community labels directamente into RAG context for better grounding.
- ✅ **System Hardening & Cache Optimization**: Implemented status-based TTL, thread-safe Batfish operations, real-time failure reporting, and developed a 'brutal' mock test suite for comprehensive regression testing.

**Next Action**: Maintain system stability by running the 'brutal' mock test suite after every change, then proceed with final paper-scale benchmark runs with the ultra-efficient 16.4x+ GraphRAG pipeline.

---

## 🔧 KEY ARCHITECTURAL DECISIONS

### 1. **Modular "Source-of-Truth" Architecture**
- All data models isolated in `src/schemas/` (e.g., `StructuredIntent`, `DeviceIntent`).
- Validation logic split into `src/validation/` (Batfish, Containerlab, GNS3) and `src/evaluation/` (HallucinationDetector).

### 2. **"Strict Grounding" Policy**
- **Incompleteness over Fabrication**: Instruct model to omit commands rather than invent syntax.
- **Citation Gating**: Every generated block must map back to a verified `source_file` in the KG.

### 3. **Graph-Driven Token Efficiency**
- **God Node Pruning**: Filter high-degree hubs (e.g., `VectorStore`) to prevent context explosion.
- **Community Budgeting**: Strict limit of 15 additional chunks per community expansion.
- **Adaptive Thresholding**: Pilot search distance > 0.55 triggers Multi-Query; otherwise, direct match is used.
- **Dynamic Few-Shot Selection**: If `pilot_dist < 0.2`, skip few-shot. If `< 0.4`, include only 1 example.
- **Lite-Path Heuristic**: Zero-RAG path for common administrative/boilerplate CLI tasks.
- **Smart Cache Management**: Status-based TTL (30 days for success, 1 hour for failures) and surgical clearing (`--clear-failed`) to minimize LLM inference costs.

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
├── scripts/               # Benchmarks and seeding scripts
├── graphify-out/          # Knowledge Graph assets (863 nodes, 189 communities)
└── devenv.nix             # Nix-based environment config
```

---

## 📊 EVALUATION RESULTS (May 2026)

### Phase 1 Research Evaluation Summary (N=35 intents)

| Mode | Strict SV | PEA (Parameter) | GNS3 CAR | Hallucination |
|------|-----------|-----------------|----------|---------------|
| Vanilla LLM | 74.3% | 80.0% | 0.0% | 25.7% |
| **RAG-NetTwin** | **80.0%** | **94.3%** | **100.0%** | **5.7%** |

*Note: PEA reached 100% in hardening tests. 16.4x token reduction achieved via GraphRAG optimizations.*

### Retrieval Benchmarks (GraphRAG vs Baseline)

| Metric | Baseline | Advanced RAG | Improvement |
| :--- | :--- | :--- | :--- |
| Mean Semantic Precision | 0.2764 | **0.4856** | **+75.6%** |
| Total Recall (Unique Chunks) | 10 | **135** | **+1250%** |
| **Tokens Per Query** | **~57,533** | **~3,503** | **16.4x Reduction** |

---

## 💡 KEY RESEARCH INNOVATIONS

1. **OS Version-Locked Retrieval**: Ensuring syntax matches specific firmware via `InventoryResolver`.
2. **Deterministic Syntactic Verification Gate**: Tier 1 validation before any execution attempt.
3. **Adaptive Community Anchoring**: Using KG community labels and budgeting to mitigate retrieval noise.
4. **Dynamic Few-Shot Selection**: Confidence-aware example injection to minimize prompt overhead.
5. **Config Acceptance Rate (CAR)**: Quantitative measurement of hardware-level syntax acceptance.

---

## ⚙️ QUICK START

```bash
# 1. Enter the environment
devenv shell

# 2. Run the brutal mock test suite (mandatory after any code change)
devenv shell pytest tests/test_brutal_system.py

# 3. Run the main evaluation (using optimized cache flags)
uv run python run_paper_eval.py               # default: uses cache
uv run python run_paper_eval.py --clear-failed # clears only failed entries
uv run python run_paper_eval.py --re-validate  # re-runs validation without LLM calls
uv run python run_paper_eval.py --clear-cache  # (use sparingly - clears all cache)

# 4. Run the retrieval benchmark
uv run python scripts/graph_retrieval_benchmark.py

# 5. Generate/Update Knowledge Graph
graphify update .

# 6. Start the UI
uv run python ui/backend/app.py
# (Then open ui/frontend/index.html)
```

---

**End Goal**: Publish a high-impact paper demonstrating that **Structured Knowledge Graphs** combined with **Strict Citation Gating** can enable production-ready Intent-Based Networking with near-zero hallucinations.
