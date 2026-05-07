# Quick Start Guide

Get RAG-NetTwin running in under 5 minutes.

## Prerequisites

- Ubuntu 22.04+ (or WSL2 on Windows)
- Python 3.10-3.11
- 16GB+ RAM
- API key from Groq or Gemini

## Step-by-Step Setup

### 1. Clone and Navigate

```bash
git clone https://github.com/yourusername/ragnet-ibn.git
cd ragnet-ibn
```

### 2. Install Python Dependencies

**Option A: Using uv (Recommended)**
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync
```

**Option B: Using pip**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your preferred editor:

```bash
# Choose your LLM provider
LLM_PROVIDER=groq  # or 'gemini'

# For Groq (Get key at https://console.groq.com/)
GROQ_API_KEY=your_groq_api_key_here

# For Gemini (Get key at https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Quick Test

```bash
# Test the CLI
uv run python main.py

# Enter a network intent when prompted:
# > Configure OSPF area 0 on Router-A interface Gig0/1
```

You should see:
- Intent parsing
- Configuration generation
- Retrieved documentation references

### 5. Install Validators (Optional but Recommended)

```bash
sudo ./scripts/install_validators_ubuntu.sh --runtime=docker
```

This installs:
- **Batfish** (Tier 1): Static analysis on port 9997
- **Containerlab** (Tier 2): Network emulation
- **GNS3** (Tier 3): Network simulation on port 3080

## Next Steps

- **Detailed Installation**: See [INSTALLATION.md](INSTALLATION.md)
- **Configuration Options**: See [CONFIGURATION.md](CONFIGURATION.md)
- **Usage Examples**: See [USAGE.md](USAGE.md)

## Common Commands

```bash
# Run CLI mode
uv run python main.py

# Run Web UI
uv run python ui/backend/app.py

# Verify validators
sudo ./scripts/install_validators_ubuntu.sh --verify

# Run evaluation benchmark
uv run python src/evaluation/evaluator.py
```

## Troubleshooting

**Import errors?**
```bash
# Ensure you're in the project root
cd /path/to/ragnet-ibn

# Verify Python version
python --version  # Should be 3.10.x or 3.11.x
```

**API key errors?**
```bash
# Check if .env file exists and has correct format
cat .env | grep API_KEY

# Validate configuration
uv run python -c "from config import validate_llm_config; validate_llm_config()"
```

**Need help?**
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Open an issue on GitHub

---

**You're all set!** 🎉 Start generating network configurations with confidence.
