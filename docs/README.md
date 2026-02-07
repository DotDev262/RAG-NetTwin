# RAG-NetTwin Documentation

**Hallucination-Mitigated Intent-Based Networking System**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

1. [Quick Start](QUICKSTART.md)
2. [Installation](INSTALLATION.md)
3. [Configuration](CONFIGURATION.md)
4. [Architecture](ARCHITECTURE.md)
5. [Usage Guide](USAGE.md)
6. [API Reference](API.md)
7. [Troubleshooting](TROUBLESHOOTING.md)
8. [Contributing](CONTRIBUTING.md)

## Project Overview

RAG-NetTwin is a research-driven Intent-Based Networking (IBN) system that leverages Retrieval-Augmented Generation (RAG) to generate accurate, vendor-verified network configurations. It specifically addresses the "hallucination" problem in LLMs by grounding all generated commands in official vendor documentation.

### Key Features

- **Multi-Provider LLM Support**: Switch between Groq and Gemini seamlessly
- **OS Version-Locked RAG**: Ensures CLI syntax accuracy for specific device versions
- **Three-Tier Validation**:
  - Tier 1 (Static): Batfish analysis for syntax and logical errors
  - Tier 2 (Emulation): Containerlab for protocol verification
  - Tier 3 (Simulation): GNS3 for full traffic testing
- **Multi-Vendor Support**: Cisco IOS-XE, Juniper JunOS
- **Zero-Hallucination Target**: Uses retrieved vendor documentation only

### System Requirements

- **OS**: Ubuntu 22.04+ (Desktop or Server)
- **Python**: 3.10-3.11
- **RAM**: 16GB+ recommended
- **Storage**: 50GB+ free space
- **Container Runtime**: Docker or Podman

### Supported LLM Providers

| Provider | Models | Free Tier | Notes |
|----------|--------|-----------|-------|
| **Groq** | Llama 3.3 70B, Mixtral | 1M tokens/day | Fast inference, good accuracy |
| **Gemini** | 1.5 Flash, 1.5 Pro | 1K requests/day | Google's model, multimodal |

### Quick Links

- [GitHub Repository](https://github.com/yourusername/ragnet-ibn)
- [Installation Guide](INSTALLATION.md)
- [Configuration Reference](CONFIGURATION.md)
- [API Documentation](API.md)

## Project Structure

```
ragnet-ibn/
├── src/
│   ├── llm/              # LLM Provider abstraction (Groq, Gemini)
│   ├── parser/           # Intent parsing (NL → Structured)
│   ├── rag/              # RAG pipeline (retrieval + generation)
│   ├── validation/       # Three-tier validation (Batfish, Containerlab, GNS3)
│   └── evaluation/       # Benchmarking and metrics
├── data/
│   ├── raw_docs/         # Vendor documentation PDFs
│   ├── processed_chunks/ # Processed documentation chunks
│   └── chroma_db/        # Vector database storage
├── scripts/
│   └── install_validators_ubuntu.sh  # Validator installation
├── tests/                # Test suite
├── docs/                 # Documentation
└── ui/                   # Web interface (FastAPI + React)
```

## Getting Started

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/ragnet-ibn.git
cd ragnet-ibn
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
# or using uv
uv sync
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 4. Install Validators (Optional)

```bash
# Install three-tier validators
sudo ./scripts/install_validators_ubuntu.sh --runtime=docker
```

### 5. Run the Application

```bash
# CLI Mode
uv run python main.py

# Web UI Mode
uv run python ui/backend/main.py
```

## Documentation Sections

### For Users
- **[Quick Start Guide](QUICKSTART.md)** - Get up and running in 5 minutes
- **[Installation Guide](INSTALLATION.md)** - Detailed installation instructions
- **[Configuration Guide](CONFIGURATION.md)** - All configuration options
- **[Usage Guide](USAGE.md)** - How to use the system

### For Developers
- **[Architecture Overview](ARCHITECTURE.md)** - System design and components
- **[API Reference](API.md)** - API documentation
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute

### Support
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[FAQ](FAQ.md)** - Frequently asked questions

## Research Context

This project is developed as a B.Tech Final Year Project with the goal of achieving:

- **< 2% hallucination rate** (vs 20-30% for vanilla LLMs)
- **> 99% syntactic accuracy**
- **> 95% semantic correctness**

### Key Innovation

**OS Version-Locked RAG with Three-Tier Validation**

Unlike general-purpose LLMs that may hallucinate CLI syntax, RAG-NetTwin:
1. Retrieves commands only from official vendor documentation
2. Locks retrieval to specific OS versions (e.g., Cisco IOS-XE 17.6)
3. Validates generated configs through static analysis, emulation, and simulation

## Citation

If you use RAG-NetTwin in your research, please cite:

```bibtex
@software{ragnettwin2025,
  title={RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking},
  author={Your Name},
  year={2025},
  url={https://github.com/yourusername/ragnet-ibn}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Acknowledgments

- **Groq** - For fast LLM inference API
- **ChromaDB** - For vector database
- **LangChain** - For LLM orchestration
- **Batfish** - For network configuration analysis
- **Containerlab** - For network emulation
- **GNS3** - For network simulation

## Support

- 📧 Email: your.email@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/ragnet-ibn/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/yourusername/ragnet-ibn/discussions)

---

**Made with ❤️ for the networking community**

*Last Updated: February 2025*
