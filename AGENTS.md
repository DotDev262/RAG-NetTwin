# AGENTS.md - Project Context for RAG-NetTwin

**Project Name**: Hallucination-Mitigated Intent-Based Networking (RAG-NetTwin)  
**Type**: B.Tech Final Year Project with Journal Publication Goal  
**Timeline**: 10 Months (5 months implementation + 5 months paper)  
**Last Updated**: May 8, 2026  

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

**Phase**: Evaluation & Research Optimization - Entering Final Paper Draft Phase
**Last Updated**: May 8, 2026

**Recent Milestones**:
- ✅ **Full Codebase Refactor**: Modularized into `src/schemas`, `src/utils`, `src/evaluation`.
- ✅ **Infrastructure Hardening**: Integrated Mypy (Static Analysis) and Ruff (Linting) into pre-commit hooks.
- ✅ **Deep Trace System**: Implemented full audit trail capturing prompts, search scores, and Telnet logs.
- ✅ **GNS3 Functional Metrics**: Implemented Config Acceptance Rate (CAR) and Interoperability Success Rate (ISR).
- ✅ **Advanced RAG**: Implemented Multi-Query, Syntax reranking, and Lost-in-the-Middle mitigation.

**Next Action**: Detailed ablation study using the new `graph` mode vs `tiered` mode.

---

## 🔧 KEY ARCHITECTURAL DECISIONS

### 1. **Modular "Source-of-Truth" Architecture**
- All data models are isolated in `src/schemas/` to prevent circular dependencies.
- Logic is partitioned into specialized packages: `parser`, `rag`, `validation`, `evaluation`.

### 2. **"Strict Grounding" Policy**
- **Incompleteness over Fabrication**: Instruct model to omit commands rather than invent syntax.
- **Parameter Binding**: Post-generation check ensures all IPs/ASNs were authorized by the Intent or Master Plan.

### 3. **Hierarchical Precision**
- **Hierarchical Anchoring**: Injects `CONTEXT: A > B > C` breadcrumbs into prompts.
- **Syntax-Aware Reranking**: Boosts relevance for documentation containing actual CLI markers.

### 4. **Fail-Fast Configuration**
- Uses `pydantic-settings` to validate environment variables and API keys immediately at startup.

---

## 🏗️ TECH STACK

### **Core**:
- **Vector DB**: ChromaDB (local)
- **Knowledge Graph**: networkx (exported from `graphify`)
- **LLM**: Llama 3.3 70B & Gemini 2.0 Flash via LangChain
- **Static Analysis**: Mypy
- **Linter/Formatter**: Ruff

### **Research Tools**:
- **Tier 1**: Batfish (Docker)
- **Tier 3**: GNS3 (Telnet-based verification)
- **Tracing**: Standalone JSON traces in `results/traces/`

---

## 📁 PROJECT STRUCTURE

```
RAG-NetTwin/
├── src/
│   ├── schemas/           # Pydantic models (Intent, Device, etc.)
│   ├── rag/               # VectorStore, QueryExpander, Normalizer, Coordinator
│   ├── parser/            # IntentParser, InventoryResolver
│   ├── validation/        # Batfish, GNS3, ReferentialIntegrity
│   ├── evaluation/        # CacheManager, StatsReporter, HallucinationDetector
│   └── utils/             # Modularized helpers (logger, text, system)
├── ui/
│   ├── frontend/          # Interactive dashboard with Visual Grounding
│   └── backend/           # FastAPI app.py
├── scripts/               # Benchmarks and seeding scripts
├── results/               # Eval reports and traces/
├── graphify-out/          # Knowledge Graph assets
└── devenv.nix             # Nix-based environment config
```

---

## 📊 EVALUATION RESULTS (May 2026)

### Phase 1 Research Evaluation Summary (N=35 intents)

| Mode | Strict SV | PEA (Parameter) | GNS3 CAR | Hallucination |
|------|-----------|-----------------|----------|---------------|
| Vanilla LLM | 74.3% | 80.0% | 0.0% | 25.7% |
| **RAG-NetTwin** | **80.0%** | **94.3%** | **100.0%** | **5.7%** |

*Note: PEA (Parameter Extraction Accuracy) reached 100% in latest hardening tests.*

### Retrieval Benchmarks (GraphRAG vs Baseline)

| Metric | Baseline | Advanced RAG | Improvement |
| :--- | :--- | :--- | :--- |
| Mean Semantic Precision | 0.2764 | **0.4856** | **+75.6%** |
| Total Recall (Unique Chunks) | 10 | **135** | **+1250%** |

---

## 💡 KEY RESEARCH INNOVATIONS

1. **OS Version-Locked Retrieval**: Ensuring syntax matches the specific firmware version.
2. **Network Master Plan**: Dynamic multi-device coordination using a two-pass generation strategy.
3. **Chain-of-Verification (Final Phase)**: Post-generation grounding audit.
4. **Visual Grounding UI**: Clickable command blocks linked to documentation source IDs.
5. **Config Acceptance Rate (CAR)**: Quantitative measurement of hardware-level syntax acceptance.

---

## ⚙️ QUICK START

```bash
# 1. Enter the environment
devenv shell

# 2. Run the main evaluation
uv run python run_paper_eval.py --clear-cache

# 3. Run the retrieval benchmark
uv run python scripts/graph_retrieval_benchmark.py

# 4. Start the UI
uv run python ui/backend/app.py
# (Then open ui/frontend/index.html)
```

---

## 📞 IF STUCK

- **Rate Limits**: Evaluation now stops automatically and reports the intent index. Check `run_paper_eval.py` logs.
- **Type Errors**: Run `uv run pre-commit run mypy --all-files`.
- **GNS3 Connection**: Verify `GNS3_HOST` in `.env` and ensure GNS3 VM is running.
- **Trace Debugging**: Inspect the latest JSON files in `results/traces/` to see raw prompts.

---

**End Goal**: Publish a high-impact paper demonstrating that **Structured Knowledge Graphs** combined with **Strict Citation Gating** can enable production-ready Intent-Based Networking with near-zero hallucinations.
