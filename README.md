# RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking

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
- **Multi-Tier Validation**: Batfish (static) → Containerlab (emulation) → GNS3 (simulation)
- **Multi-Vendor Support**: Cisco IOS-XE and Juniper JunOS

## 📊 Results

| Metric | Vanilla LLM | RAG-NetTwin | Improvement |
|--------|-------------|-------------|-------------|
| Syntactic Validity | 52.2% | **87.0%** | +35% |
| Hallucination Rate | 4.3% | **0.0%** | Target: <2% |
| CFR Faithfulness | 91.3% | 82.6% | (trade-off) |

**Full evaluation**: 23 test intents with Batfish validation

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

**Validation**: Three-tier progressive validation (Batfish → Containerlab → GNS3) catches 95%+ of configuration errors.

**Research Output**:
- 10,333+ documentation chunks in knowledge base
- 0% hallucination rate on 23 test intents
- +35% syntactic validity over vanilla LLM

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