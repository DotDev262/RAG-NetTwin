# Configuration Guide

Complete configuration reference for RAG-NetTwin.

## Configuration Files

### Primary Configuration

All configuration is managed through environment variables in the `.env` file.

```bash
# Copy the example file
cp .env.example .env

# Edit configuration
nano .env
```

### Configuration Loading Order

1. `.env` file in project root
2. System environment variables
3. Default values in `src/config.py`

## LLM Provider Configuration

### Choosing a Provider

```bash
# In .env
LLM_PROVIDER=groq  # Options: groq, gemini
```

### Groq Configuration

```bash
# Required
GROQ_API_KEY=gsk_your_api_key_here

# Optional (with defaults)
GROQ_MODEL=openai/gpt-oss-120b  # Model name
# Other options: openai/gpt-oss-20b, meta-llama/llama-4-scout-17b-16e-instruct
```

**Available Groq Models:**
- `openai/gpt-oss-120b` (Recommended - best accuracy)
- `openai/gpt-oss-20b` (Fast, good accuracy)
- `meta-llama/llama-4-scout-17b-16e-instruct` (Larger context window)

**Groq Limits:**
- Free tier: 1M tokens/day
- Rate limit: Depends on model

### Gemini Configuration

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (with defaults)
GEMINI_MODEL=gemini-1.5-flash  # Model name
# Other options: gemini-1.5-pro
```

**Available Gemini Models:**
- `gemini-1.5-flash` (Fast, cost-effective)
- `gemini-1.5-pro` (Higher quality, more expensive)

**Gemini Limits:**
- Free tier: 1,500 requests/day
- Rate limit: 15 requests/minute (free tier)

### Switching Providers

To switch between providers, simply change `LLM_PROVIDER`:

```bash
# Switch to Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here

# Switch back to Groq
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

No code changes required!

## Vector Database Configuration

### ChromaDB Settings

```bash
# Storage location
CHROMA_PERSIST_DIR=./data/chroma_db

# Collection name
CHROMA_COLLECTION_NAME=network_docs

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**Available Embedding Models:**
- `all-MiniLM-L6-v2` (Default - fast, good quality)
- `all-mpnet-base-v2` (Higher quality, slower)
- `all-MiniLM-L12-v2` (Balanced)

### Retrieval Settings

```bash
# Number of results to retrieve per query
TOP_K_RETRIEVAL=5

# Enable OS version filtering
ENABLE_VERSION_LOCK=true

# Strict version matching
STRICT_VERSION_MATCH=true
```

## Three-Tier Validation Configuration

### Tier 1: Batfish

```bash
# Host and port
BATFISH_HOST=localhost
BATFISH_PORT=8888

# Alternative ports (if using Docker)
# BATFISH_HOST=localhost
# BATFISH_PORT=9997
```

### Tier 2: Containerlab

```bash
# Enable/disable
CONTAINERLAB_ENABLED=true

# Timeout in seconds
CONTAINERLAB_TIMEOUT=30
```

### Tier 3: GNS3

```bash
# Enable/disable
GNS3_ENABLED=true

# Server connection
GNS3_HOST=localhost
GNS3_PORT=3080

# Project storage
GNS3_PROJECT_PATH=./gns3_projects
```

## Data Paths

### Directory Structure

```bash
# Raw documentation (PDFs)
RAW_DOCS_PATH=./data/raw_docs

# Processed chunks (JSON)
PROCESSED_CHUNKS_PATH=./data/processed_chunks

# Generated configurations
GENERATED_CONFIGS_PATH=./data/configs

# Vector database
CHROMA_DB_PATH=./data/chroma_db
```

### WSL Path Handling

If using WSL, paths are automatically converted:

```bash
# Windows paths are converted to WSL format
# C:\Users\Name\Documents → /mnt/c/Users/Name/Documents
```

## Network Device Defaults

### Default Settings

```bash
# Default vendor
DEFAULT_VENDOR=Cisco

# Default OS
DEFAULT_OS=IOS-XE

# Default OS version
DEFAULT_OS_VERSION=17.6
```

These are used when the intent parser cannot determine device specifics.

## Application Settings

### Web Interface

```bash
# Flask/FastAPI configuration
FLASK_ENV=development
FLASK_DEBUG=true
API_PORT=5000
API_HOST=127.0.0.1

# For production
# FLASK_ENV=production
# FLASK_DEBUG=false
# API_HOST=0.0.0.0
```

### Logging

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log file location
LOG_FILE=./logs/ragnet.log

# Log rotation
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5
```

## Advanced Configuration

### Custom System Prompts

Edit `src/rag/config_generator.py`:

```python
def _get_system_prompt(self) -> str:
    return """Your custom system prompt here..."""
```

### Temperature and Sampling

```bash
# In src/config.py
class Settings(BaseModel):
    temperature: float = 0.0  # 0.0 = deterministic, 1.0 = creative
```

### Chunking Parameters

```bash
# In .env or src/config.py
CHUNK_SIZE=512        # Tokens per chunk
CHUNK_OVERLAP=50      # Overlap between chunks
```

### Retrieval Parameters

```python
# In src/rag/config_generator.py
# Tier 1 retrieval (syntax)
context_tier1 = self.vector_store.retrieve(
    query=query, 
    os_version=search_version,
    tier=1,
    n_results=10
)

# Tier 2 retrieval (patterns)
context_tier2 = self.vector_store.retrieve(
    query=query,
    os_version=search_version,
    tier=2,
    n_results=5
)
```

## Environment-Specific Configuration

### Development

```bash
FLASK_ENV=development
FLASK_DEBUG=true
LOG_LEVEL=DEBUG
```

### Production

```bash
FLASK_ENV=production
FLASK_DEBUG=false
LOG_LEVEL=WARNING
API_HOST=0.0.0.0
```

### Testing

```bash
# Use mock LLM for testing
LLM_PROVIDER=groq
GROQ_API_KEY=test_key
LOG_LEVEL=DEBUG
```

## Configuration Validation

### Check Configuration

```bash
# Validate LLM configuration
uv run python -c "from config import validate_llm_config; validate_llm_config()"

# View current settings
uv run python -c "from config import settings; print(settings)"
```

### Common Validation Errors

**Error: `GROQ_API_KEY not found`**
```bash
# Solution: Add API key to .env
echo "GROQ_API_KEY=your_key_here" >> .env
```

**Error: `Unsupported LLM provider`**
```bash
# Solution: Use supported provider
LLM_PROVIDER=groq  # or gemini
```

**Error: `Directory not found`**
```bash
# Solution: Create required directories
mkdir -p data/raw_docs data/processed_chunks data/configs data/chroma_db
```

## Configuration Examples

### Minimal Configuration

```bash
# .env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

### Full Configuration

```bash
# LLM Provider
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxx
GROQ_MODEL=openai/gpt-oss-120b

# Gemini backup (optional)
GEMINI_API_KEY=xxxxxxxx
GEMINI_MODEL=gemini-1.5-flash

# Data paths
CHROMA_PERSIST_DIR=./data/chroma_db
RAW_DOCS_PATH=./data/raw_docs
PROCESSED_CHUNKS_PATH=./data/processed_chunks

# Validation
BATFISH_HOST=localhost
BATFISH_PORT=9997
GNS3_HOST=localhost
GNS3_PORT=3080

# Application
FLASK_ENV=development
API_PORT=5000
LOG_LEVEL=INFO
```

### Multi-Provider Setup

```bash
# Primary: Groq
LLM_PROVIDER=groq
GROQ_API_KEY=primary_key

# Fallback: Gemini (manual switch)
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=backup_key
```

## Next Steps

- **[Usage Guide](USAGE.md)** - Learn how to use the system
- **[API Reference](API.md)** - API documentation
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues

---

**Need help?** Check the [Troubleshooting Guide](TROUBLESHOOTING.md) or open an issue on GitHub.
