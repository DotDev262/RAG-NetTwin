# RAG-NetTwin: Retrieval-Augmented Generation for Network Configuration Validation

A research system that synthesizes network CLI configurations from natural language intents using GraphRAG, multi-vendor knowledge graphs, and three-tier validation to minimize LLM hallucinations.

**Evaluated on**: Cisco IOS-XE 17.6, Juniper JunOS 21.4 (35 intents)

---

## Key Results (N=35, 95% Bootstrap CI)

| Metric | Vanilla LLM | RAG-NetTwin |
|--------|-------------|-------------|
| Strict Syntactic Validity (SV) | 74.3% | **94.3%** [85.7%, 100.0%] |
| Hallucination Rate (HR) | 25.7% | **2.9%** |
| Parameter Extraction Accuracy (PEA) | 80.0% | **100.0%** |
| GNS3 Command Accuracy Rate (CAR) | 0.0% | **82.9%** [68.6%, 94.3%] |
| Intent Syntactic Recognition (ISR) | 0.0% | **100.0%** |

**Token reduction**: 16.4x vs baseline RAG (57,533 → 3,503 tokens/query)

---

## Key Features

- **GraphRAG**: Hierarchical knowledge graph (1,334 nodes, 162 communities, 13.5 avg degree)
- **Mandatory Citation Refinement**: Every generated command includes a verifiable documentation citation
- **Version-Locked Retrieval**: Filters by OS version (IOS-XE 17.6, JunOS 21.4)
- **Three-Tier Validation**:
  - **Tier 1**: Batfish static analysis (syntax validation)
  - **Tier 2**: Referential Integrity (parameter-command consistency)
  - **Tier 3**: Network Master Plan (GNS3 functional simulation)
- **Multi-Vendor**: Cisco IOS-XE, Juniper JunOS
- **API Key Rotation**: Automatic rotation across multiple Groq API keys on rate limit

---

## Quick Start

```bash
git clone https://github.com/your-repo/RAG-NetTwin.git
cd RAG-NetTwin

python -m venv .venv && source .venv/bin/activate
uv sync
```

**Requirements:** Python 3.10+, Groq API key, Docker (for Batfish/GNS3)

---

## Running Evaluation

```bash
# Paper evaluation (35 intents, three-tier validation)
uv run python run_paper_eval.py --run-gns3

# Strict Verification Mode (short-circuits GNS3 on Batfish failure)
uv run python run_paper_eval.py --run-gns3

# Observational Mode (pushes unvalidated configs to study hardware impact)
uv run python run_paper_eval.py --run-gns3 --evaluation-mode observational

# Retrieval benchmark
uv run python benchmarks/graph_retrieval_benchmark.py

# Unit tests
uv run pytest
```

---

## Project Structure

```
RAG-NetTwin/
├── benchmarks/           # Performance comparison scripts
├── paper-analysis/       # Results analysis, figures, statistics
│   ├── generate_paper_figures.py
│   ├── statistical_analysis.py   # Bootstrap CIs, Wilcoxon, 5-fold CV
│   ├── hyperparameter_ablation.py
│   └── figures/          # Generated paper figures (300 DPI JPG)
├── src/
│   ├── rag/              # GraphRAG config generation, vector store
│   ├── validation/       # Batfish/GNS3 validators
│   └── evaluation/       # Hallucination detection
├── data/
│   ├── graph_corpus/     # Cisco/Juniper CLI documentation corpus
│   ├── graph_db/         # Knowledge graph (JSON, chunk mappings)
│   └── chroma_db/        # Vector embeddings
└── run_paper_eval.py     # Main evaluation engine
```

---

## Statistical Rigor

- **Bootstrap CIs**: 95% confidence intervals (N=1000 resamples)
- **Wilcoxon signed-rank**: p<0.001 for all metrics vs baseline
- **Cohen's d**: 1.22 (SV), 3.11 (CAR), 4.12 (HR-Free)
- **5-fold cross-validation**: Reported as mean ± std
- **Hyperparameter ablation**: Community budget=15, cosine threshold=0.70

---

## License

MIT License — See LICENSE file
