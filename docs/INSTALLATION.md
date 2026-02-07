# Installation Guide

Complete installation instructions for RAG-NetTwin.

## System Requirements

### Minimum Requirements
- **OS**: Ubuntu 20.04+ (or WSL2 on Windows 10/11)
- **Python**: 3.10-3.11 (Python 3.12+ not yet supported)
- **RAM**: 16GB minimum (32GB recommended for large-scale evaluation)
- **Storage**: 50GB free space
- **Network**: Internet connection for API calls and Docker images

### Recommended Hardware
- **CPU**: 4+ cores (8+ cores for parallel processing)
- **RAM**: 32GB or more
- **Storage**: SSD with 100GB+ free space
- **GPU**: Not required (CPU-only operation)

## Installation Methods

### Method 1: Automated Installation (Recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/ragnet-ibn.git
cd ragnet-ibn

# Run automated setup
./scripts/setup.sh
```

### Method 2: Manual Installation

#### Step 1: System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and build tools
sudo apt install -y python3.10 python3.10-venv python3.10-dev python3-pip
sudo apt install -y build-essential git curl wget

# Install additional tools
sudo apt install -y poppler-utils tesseract-ocr
```

#### Step 2: Python Environment

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

**OR using uv (faster):**

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Sync dependencies (uses pyproject.toml)
uv sync
```

#### Step 3: Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env  # or use your preferred editor
```

Required environment variables:
```bash
# LLM Provider (groq or gemini)
LLM_PROVIDER=groq

# API Keys (at least one required)
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here
```

#### Step 4: Install Validators (Optional)

```bash
# Install three-tier validators
sudo ./scripts/install_validators_ubuntu.sh --runtime=docker

# Verify installation
sudo ./scripts/install_validators_ubuntu.sh --verify
```

### Method 3: Docker Installation

```bash
# Build Docker image
docker build -t ragnet-ibn .

# Run container
docker run -it --rm \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/data:/app/data \
  -p 5000:5000 \
  ragnet-ibn
```

## Post-Installation Setup

### 1. Verify Installation

```bash
# Check Python version
python --version  # Should show 3.10.x

# Test imports
uv run python -c "from config import settings; print('✓ Config loaded')"
uv run python -c "from llm import LLMProvider; print('✓ LLM Provider ready')"

# Validate LLM configuration
uv run python -c "from config import validate_llm_config; validate_llm_config()"
```

### 2. Download Documentation (Optional)

```bash
# Download Cisco documentation
python scripts/download_cisco_docs.py

# Download Juniper documentation
python scripts/download_juniper_docs.py
```

### 3. Process Documentation

```bash
# Extract and chunk documentation
python scripts/extract_pdfs.py
python scripts/chunk_docs.py
```

### 4. Populate Vector Database

```bash
# Import chunks into ChromaDB
python src/data_processing/pipeline.py
```

## Platform-Specific Instructions

### Ubuntu Desktop

No additional steps required. Follow standard installation above.

### WSL2 (Windows)

```bash
# Enable systemd (if not already enabled)
sudo nano /etc/wsl.conf
```

Add:
```ini
[boot]
systemd=true
```

```bash
# Restart WSL
wsl --shutdown
# Restart your WSL terminal

# Continue with standard installation
```

**Note for Docker in WSL:**
- Use Docker Desktop with WSL2 integration
- Or install Docker inside WSL: `sudo ./scripts/install_validators_ubuntu.sh --runtime=docker`

### macOS (Limited Support)

RAG-NetTwin is primarily designed for Linux. macOS support is experimental:

```bash
# Install Homebrew dependencies
brew install python@3.10 poppler tesseract

# Follow manual installation steps
# Some validators (GNS3) may not work on macOS
```

## Troubleshooting Installation

### Python Version Issues

```bash
# Check installed Python versions
ls -la /usr/bin/python*

# Install Python 3.10 specifically
sudo apt install python3.10 python3.10-venv python3.10-dev

# Use update-alternatives (optional)
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1
```

### Permission Denied Errors

```bash
# Fix permissions
sudo chown -R $USER:$USER /path/to/ragnet-ibn

# Or run with proper permissions
chmod +x scripts/*.sh
```

### Package Installation Failures

```bash
# Clear pip cache
pip cache purge

# Install with verbose output
pip install -r requirements.txt -v

# For specific package issues
pip install --no-cache-dir <package-name>
```

### Import Errors

```bash
# Ensure you're in the project root
cd /path/to/ragnet-ibn

# Check Python path
uv run python -c "import sys; print('\n'.join(sys.path))"

# Verify src is in path
echo $PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

## Next Steps

After successful installation:

1. **[Configuration](CONFIGURATION.md)** - Customize settings
2. **[Usage Guide](USAGE.md)** - Learn how to use the system
3. **[Architecture](ARCHITECTURE.md)** - Understand the system design

## Getting Help

- **Installation Issues**: Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub Issues**: [Report problems](https://github.com/yourusername/ragnet-ibn/issues)
- **Discussions**: [Ask questions](https://github.com/yourusername/ragnet-ibn/discussions)

---

**Installation complete?** Run `uv run python main.py` to start using RAG-NetTwin!
