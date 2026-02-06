# RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking

RAG-NetTwin is a research-driven Intent-Based Networking (IBN) system that leverages Retrieval-Augmented Generation (RAG) to generate accurate, vendor-verified network configurations. It specifically addresses the "hallucination" problem in LLMs by grounding all generated commands in official vendor documentation.

## 🚀 Key Features
- **Zero-Hallucination Target**: Uses OS version-locked RAG to ensure CLI syntax accuracy.
- **Multi-Vendor Support**: Support for Cisco IOS-XE and Juniper JunOS.
- **Three-Tier Validation**:
    - **Tier 1 (Static)**: Batfish analysis for syntax and logical errors.
    - **Tier 2 (Emulation)**: Containerlab (WSL2) for protocol verification.
    - **Tier 3 (Simulation)**: GNS3 integration for full traffic testing.
- **WSL2 Optimized**: Smart host detection and path resolution for seamless Windows/Linux operation.
- **Structured Logging**: JSON-based logging for research observability.

## 📁 Project Structure
- `src/`: Core logic (Parser, RAG, Validation, Evaluation).
- `data/`: Vector database (ChromaDB) and raw documentation.
- `scripts/`: WSL and GNS3 setup utilities.
- `ui/`: FastAPI backend and Dashboard frontend.
- `tests/`: End-to-end and component-specific tests.

## 🛠️ Quick Start

### 1. Prerequisites
- Python 3.10+
- Docker Desktop (with WSL2)
- Groq API Key

### 2. Setup
```bash
# Install dependencies
uv sync

# Setup WSL Environment (for validation)
cd scripts
./setup_wsl.sh
./setup_gns3_wsl.sh
```

### 3. Usage
**CLI Mode:**
```bash
uv run python main.py
```

**UI Mode:**
```bash
uv run python ui/backend/main.py
```

## 📊 Evaluation
To run the benchmark comparing RAG vs. Vanilla LLM performance:
```bash
uv run python src/evaluation/evaluator.py
```

## 📜 License
MIT License
