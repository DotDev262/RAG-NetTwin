# RAG-NetTwin: Project Summary & Status

**Date**: 06 February 2026
**Status**: Optimized & Refactored (Phase 3 Complete)

## 1. Project Overview
RAG-NetTwin is a research system designed to eliminate "hallucinations" (fabrications) in LLM-generated network configurations. It uses **Retrieval-Augmented Generation (RAG)** to ground an LLM (Llama 3.3 via Groq) in official vendor documentation, ensuring every generated command is cited and accurate.

## 2. Key Accomplishments
- **Multi-Vendor Support**: Fully operational for **Cisco IOS-XE** and **Juniper JunOS**.
- **Documentation Ingestion**: 1,690 chunks of verified vendor knowledge indexed in ChromaDB with `all-MiniLM-L6-v2` embeddings.
- **Hallucination Mitigation**: System refuses to generate configs if documentation is missing ("INSUFFICIENT_CONTEXT").
- **Multi-Tier Validation**:
  - **Tier 1**: Static Analysis via Batfish (Docker/WSL2).
  - **Tier 2**: Emulation via Containerlab (WSL2 native support).
  - **Tier 3**: Full Simulation via GNS3 (API Integration with smart host detection).
- **Centralized Architecture**: Unified configuration using Pydantic and abstract base classes for validators.

## 3. Directory Structure
```
RAG-NetTwin/
├── data/
│   ├── raw_docs/           # PDF Documentation (Cisco/Juniper)
│   ├── processed_chunks/   # JSON chunks for debugging
│   └── chroma_db/          # Vector Database (The "Brain")
├── src/
│   ├── config.py           # Centralized Pydantic Settings
│   ├── logger.py           # Structured JSON Logging
│   ├── data_processing/    # Pipeline: PDF -> Text -> Chunks -> DB
│   ├── parser/             # Intent Parser (NL -> JSON)
│   ├── rag/                # Config Generator & Vector Store
│   ├── validation/         # Validators (Batfish, Containerlab, GNS3)
│   └── evaluation/         # Benchmark Suite (RAG vs Vanilla)
├── scripts/                # Setup and utility scripts (WSL, GNS3, Downloads)
├── ui/
│   ├── backend/            # FastAPI Server with Input Validation
│   └── frontend/           # HTML/JS Dashboard
├── tests/                  # Verification Scripts
└── main.py                 # CLI Entry Point
```

## 4. How to Compare (RAG vs. Vanilla)
The project includes a specific tool to measure the improvement over a standard LLM:

**Run the Benchmark:**
```bash
uv run python src/evaluation/evaluator.py
```

**What it does:**
1. Takes a set of network scenarios (e.g., "Configure OSPF...").
2. Generates a config using **Vanilla Llama 3** (No Docs).
3. Generates a config using **RAG-NetTwin** (With Docs).
4. Calculates metrics:
   - **Time**: RAG is slower (due to retrieval) - this is the trade-off.
   - **Hallucination Score**: Heuristic based on citations and syntax checking.
5. Saves results to `results/benchmark_report.json`.

## 5. Next Steps for Research
1. **Expand Dataset**: Add more complex intents to `src/evaluation/evaluator.py`.
2. **Run Batfish on Baseline**: Use `BatfishValidator` to check the *Vanilla* output. You will likely see syntax errors that RAG avoids.
3. **Paper Writing**: Use the data from `results/` to build your comparative tables.
