# Troubleshooting Guide

Common issues and their solutions.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Configuration Issues](#configuration-issues)
3. [Runtime Issues](#runtime-issues)
4. [LLM Provider Issues](#llm-provider-issues)
5. [Validation Issues](#validation-issues)
6. [Performance Issues](#performance-issues)

## Installation Issues

### Python Version Errors

**Error:** `Python 3.12 not supported`

**Solution:**
```bash
# Install Python 3.10
sudo apt install python3.10 python3.10-venv python3.10-dev

# Use Python 3.10
python3.10 -m venv venv
source venv/bin/activate
```

**Error:** `No module named 'venv'`

**Solution:**
```bash
# Install venv package
sudo apt install python3.10-venv

# Or use virtualenv
pip install virtualenv
virtualenv -p python3.10 venv
```

### Dependency Installation Failures

**Error:** `Failed building wheel for chroma-hnswlib`

**Solution:**
```bash
# Install build dependencies
sudo apt install build-essential python3-dev

# Clear pip cache
pip cache purge

# Install with verbose output to see errors
pip install chromadb -v
```

**Error:** `Could not find a version that satisfies the requirement`

**Solution:**
```bash
# Upgrade pip
pip install --upgrade pip

# Try with uv (more reliable)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

**Error:** `ImportError: cannot import name 'ChatGroq'`

**Solution:**
```bash
# Reinstall langchain-groq
pip uninstall langchain-groq -y
pip install langchain-groq>=1.1.2

# Verify installation
uv run python -c "from langchain_groq import ChatGroq; print('✓ OK')"
```

### Permission Errors

**Error:** `Permission denied: '/usr/local/lib/python3.10'`

**Solution:**
```bash
# Use virtual environment (recommended)
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Or install as user (not recommended)
pip install --user -r requirements.txt
```

**Error:** `Permission denied when running scripts`

**Solution:**
```bash
# Fix script permissions
chmod +x scripts/*.sh

# Or run with bash
bash scripts/install_validators_ubuntu.sh
```

## Configuration Issues

### API Key Errors

**Error:** `GROQ_API_KEY not found in settings`

**Solution:**
```bash
# 1. Check if .env file exists
ls -la .env

# 2. Create from example
cp .env.example .env

# 3. Edit and add your key
nano .env
# Add: GROQ_API_KEY=gsk_your_actual_key_here

# 4. Verify configuration
uv run python -c "from config import settings; print(settings.groq_api_key[:10] + '...')"
```

**Error:** `GEMINI_API_KEY required when using provider 'gemini'`

**Solution:**
```bash
# Edit .env
nano .env

# Set provider and key
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here

# Or switch back to Groq
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
```

### LLM Provider Validation Errors

**Error:** `Unsupported LLM provider: 'openai'`

**Solution:**
```bash
# Use supported provider
LLM_PROVIDER=groq  # or 'gemini'
```

**Error:** `ValueError: LLM configuration validation failed`

**Solution:**
```bash
# Check current settings
uv run python << 'EOF'
from config import settings
print(f"Provider: {settings.llm_provider}")
print(f"Groq API Key: {'✓ Set' if settings.groq_api_key else '✗ Missing'}")
print(f"Gemini API Key: {'✓ Set' if settings.gemini_api_key else '✗ Missing'}")
EOF

# Fix based on output
```

### Environment Variable Issues

**Error:** `dotenv.load_dotenv() not finding .env`

**Solution:**
```bash
# Ensure .env is in project root
pwd  # Should show .../ragnet-ibn
ls .env  # Should exist

# Or set env vars directly
export GROQ_API_KEY=your_key_here
export LLM_PROVIDER=groq
```

**Error:** `CHROMA_PERSIST_DIR not found`

**Solution:**
```bash
# Create directories
mkdir -p data/chroma_db data/raw_docs data/processed_chunks

# Or update path in .env
CHROMA_PERSIST_DIR=/absolute/path/to/data/chroma_db
```

## Runtime Issues

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'parser'`

**Solution:**
```bash
# Ensure you're in project root
cd /path/to/ragnet-ibn

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or use uv which handles paths
uv run python main.py
```

**Error:** `ModuleNotFoundError: No module named 'config'`

**Solution:**
```bash
# Run from project root
python main.py

# NOT from src/ directory
cd /path/to/ragnet-ibn
python main.py
```

### Vector Database Issues

**Error:** `ChromaDB collection not found`

**Solution:**
```bash
# Check if vector DB exists
ls data/chroma_db/

# If empty, populate it
python src/data_processing/pipeline.py

# Or create collection manually
uv run python << 'EOF'
from rag.vector_store import VectorStore
store = VectorStore()
print(f"Collection count: {store.get_stats()}")
EOF
```

**Error:** `chromadb.errors.NotFoundError: Collection not found`

**Solution:**
```bash
# Reinitialize vector store
rm -rf data/chroma_db/*

# Process documents again
python scripts/extract_pdfs.py
python scripts/chunk_docs.py
python src/data_processing/pipeline.py
```

### Intent Parsing Errors

**Error:** `ValidationError: Intent parsing failed`

**Solution:**
```bash
# Test with simpler intent
# ❌ Complex: "Configure OSPF, BGP, and VLANs on Router-A"
# ✅ Simple: "Configure OSPF area 0 on Router-A"

# Check LLM is responding
uv run python << 'EOF'
from llm import LLMProvider
llm = LLMProvider.get_llm()
response = llm.invoke("Hello")
print(response.content)
EOF
```

## LLM Provider Issues

### Groq Issues

**Error:** `groq.RateLimitError: Rate limit exceeded`

**Solution:**
```bash
# Wait before retrying (rate limit: 1M tokens/day)
# Or switch to Gemini temporarily

# Check usage
# Visit https://console.groq.com/ to monitor usage
```

**Error:** `groq.AuthenticationError: Invalid API key`

**Solution:**
```bash
# Verify key format (should start with 'gsk_')
echo $GROQ_API_KEY

# Get new key from https://console.groq.com/
# Update .env with correct key
```

**Error:** `groq.NotFoundError: Model not found`

**Solution:**
```bash
# Check available models
# Update GROQ_MODEL in .env
GROQ_MODEL=openai/gpt-oss-120b  # or openai/gpt-oss-20b
```

### Gemini Issues

**Error:** `google.api_core.exceptions.PermissionDenied: 403`

**Solution:**
```bash
# Check API key is valid
# Visit https://aistudio.google.com/app/apikey

# Enable Gemini API in Google Cloud Console
```

**Error:** `google.api_core.exceptions.ResourceExhausted: 429`

**Solution:**
```bash
# Rate limit: 15 requests/minute (free tier)
# Wait and retry

# Or switch to Groq
LLM_PROVIDER=groq
```

**Error:** `ImportError: langchain_google_genai not found`

**Solution:**
```bash
# Install missing dependency
pip install langchain-google-genai>=1.0.0

# Or sync with uv
uv sync
```

## Validation Issues

### Batfish Issues

**Error:** `Connection refused to Batfish on port 9997`

**Solution:**
```bash
# Check if Batfish is running
docker ps | grep batfish

# Start Batfish
docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish

# Or use systemd
sudo systemctl start batfish
sudo systemctl status batfish
```

**Error:** `Batfish container exited`

**Solution:**
```bash
# Check logs
docker logs batfish

# Restart with more memory
docker rm -f batfish
docker run -d --name batfish -p 9997:9997 -p 9996:9996 \
  --memory=4g \
  batfish/batfish
```

### Containerlab Issues

**Error:** `containerlab: command not found`

**Solution:**
```bash
# Install Containerlab
sudo ./scripts/install_validators_ubuntu.sh --tier2

# Or manually
curl -sL https://containerlab.dev/setup | sudo -E bash -s "all"
```

**Error:** `Error: Failed to deploy lab`

**Solution:**
```bash
# Check Docker is running
sudo systemctl status docker

# Verify permissions
sudo usermod -aG docker $USER
# Log out and back in

# Test Docker
sudo docker run hello-world
```

### GNS3 Issues

**Error:** `Cannot connect to GNS3 server on port 3080`

**Solution:**
```bash
# Check if GNS3 is running
sudo systemctl status gns3-server

# Start GNS3
sudo systemctl start gns3-server

# Check for errors
sudo journalctl -u gns3-server -f
```

**Error:** `KVM acceleration not available`

**Solution:**
```bash
# Check KVM support
sudo apt install cpu-checker
kvm-ok

# If not supported, enable nested virtualization
# Or use GNS3 without KVM (slower)
```

## Performance Issues

### Slow Generation

**Issue:** Generation takes >30 seconds

**Solutions:**

1. **Check Internet Connection**
```bash
ping google.com
```

2. **Switch to Faster Provider**
```bash
# Groq is generally faster than Gemini
LLM_PROVIDER=groq
```

3. **Reduce Retrieval Results**
```python
# In src/rag/config_generator.py
# Reduce n_results
context_tier1 = self.vector_store.retrieve(
    query=query,
    n_results=5  # Reduced from 10
)
```

4. **Use Local Vector DB**
```bash
# Ensure ChromaDB is local, not remote
CHROMA_PERSIST_DIR=./data/chroma_db  # Local path
```

### High Memory Usage

**Issue:** System runs out of memory

**Solutions:**

1. **Limit ChromaDB Memory**
```bash
# Use memory-mapped files
export CHROMA_MEMORY_LIMIT=2G
```

2. **Close Unused Validators**
```bash
# Stop validators when not needed
sudo systemctl stop batfish gns3-server
sudo docker stop batfish 2>/dev/null
```

3. **Process Documents in Batches**
```bash
# Instead of processing all at once
python scripts/chunk_docs.py --batch-size=100
```

### Disk Space Issues

**Issue:** Running out of disk space

**Solutions:**

1. **Clean Docker**
```bash
# Remove unused containers and images
docker system prune -af

# Remove specific images
docker rmi batfish/batfish
```

2. **Clean Vector DB**
```bash
# Remove and reinitialize (only if needed)
rm -rf data/chroma_db/*
```

3. **Archive Old Results**
```bash
# Move old evaluations
mv results/ results_backup_$(date +%Y%m%d)
mkdir results
```

## Getting More Help

### Debug Mode

Enable debug logging:

```bash
# In .env
LOG_LEVEL=DEBUG

# Run with verbose output
uv run python main.py 2>&1 | tee debug.log
```

### System Information

Gather system info for bug reports:

```bash
# Create system report
uv run python << 'EOF'
import sys
import platform
from config import settings

print("=== System Information ===")
print(f"Python: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Processor: {platform.processor()}")
print()
print("=== RAG-NetTwin Configuration ===")
print(f"Provider: {settings.llm_provider}")
print(f"Groq Key: {'✓ Set' if settings.groq_api_key else '✗ Missing'}")
print(f"Gemini Key: {'✓ Set' if settings.gemini_api_key else '✗ Missing'}")
EOF
```

### Log Files

Check logs for errors:

```bash
# Application logs
tail -f logs/ragnet.log

# System logs
sudo journalctl -u batfish -f
sudo journalctl -u gns3-server -f

# Docker logs
docker logs -f batfish
```

### Community Support

- **GitHub Issues:** https://github.com/yourusername/ragnet-ibn/issues
- **GitHub Discussions:** https://github.com/yourusername/ragnet-ibn/discussions
- **Email:** your.email@example.com

### Reporting Bugs

When reporting bugs, include:

1. Error message (full traceback)
2. System information (Python version, OS)
3. Configuration (`.env` contents without API keys)
4. Steps to reproduce
5. Debug logs

---

**Still stuck?** Check [FAQ.md](FAQ.md) or open an issue on GitHub.
