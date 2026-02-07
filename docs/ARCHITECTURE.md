# Architecture Overview

System design and component architecture of RAG-NetTwin.

## System Overview

RAG-NetTwin follows a modular, pipeline-based architecture with three main stages:

1. **Intent Parsing** (NL → Structured)
2. **RAG-based Generation** (Retrieval + LLM)
3. **Three-Tier Validation** (Static → Emulation → Simulation)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Natural Lang.  │────▶│  Intent Parser   │────▶│ Structured Intent│
│     Input       │     │    (LLM)         │     │   (Pydantic)     │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RAG Pipeline                                    │
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │   Query      │  │   Vector    │  │      LLM Generation         │ │
│  │  Formation   │─▶│   Search    │─▶│  (Groq/Gemini + Context)    │ │
│  └──────────────┘  └─────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Three-Tier Validation                             │
│                                                                      │
│  Tier 1: Batfish (Static)  ──▶  Tier 2: Containerlab (Emulation)   │
│  - Syntax validation          ──▶  - Protocol verification          │
│  - Logical analysis              - Topology testing                  │
│                                    - Configuration deployment        │
│                                                                      │
│                                    Tier 3: GNS3 (Simulation)         │
│                                    - Full traffic testing            │
│                                    - Production-like validation      │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Intent Parser (`src/parser/`)

**Purpose:** Convert natural language to structured intent objects.

**Components:**
- `IntentParser` class: Main parsing logic
- `StructuredIntent` model: Pydantic schema for structured data
- `DeviceIntent` model: Device-specific parameters

**Flow:**
```
Natural Language ──▶ LLM (with structured output) ──▶ StructuredIntent
```

**Supported Providers:**
- Groq (Llama 3.3 70B)
- Gemini (1.5 Flash/Pro)

### 2. LLM Provider (`src/llm/`)

**Purpose:** Abstract LLM interactions across multiple providers.

**Key Features:**
- Provider factory pattern
- Automatic provider detection
- Structured output support
- API key validation

**Architecture:**
```python
class LLMProvider:
    @staticmethod
    def get_llm(provider, model, temperature, api_key)
    
    @staticmethod
    def get_structured_llm(schema, provider, model, temperature)
```

**Supported Providers:**
| Provider | Class | Method |
|----------|-------|--------|
| Groq | `ChatGroq` | `with_structured_output()` |
| Gemini | `ChatGoogleGenerativeAI` | `with_structured_output()` |

### 3. RAG Pipeline (`src/rag/`)

**Purpose:** Generate configurations using retrieved documentation.

**Components:**
- `ConfigGenerator`: Main generation logic
- `VectorStore`: ChromaDB interface
- Context retrieval from Tier 1 & Tier 2 chunks

**Retrieval Strategy:**
1. **Tier 1 (Syntax):** Command-level documentation
   - High precision, low recall
   - OS version-specific
   
2. **Tier 2 (Patterns):** Configuration patterns
   - Contextual examples
   - Best practices

**Flow:**
```
StructuredIntent ──▶ Query Formation ──▶ Vector Search (Tier 1+2)
                                            │
                                            ▼
Context + Prompt ──▶ LLM ──▶ Generated Config
```

### 4. Vector Database (`src/rag/vector_store.py`)

**Purpose:** Store and retrieve documentation chunks.

**Technology:** ChromaDB with Sentence Transformers embeddings

**Schema:**
```python
{
    "id": "chunk_uuid",
    "text": "command documentation",
    "metadata": {
        "tier": 1/2/3,
        "vendor": "cisco",
        "os_version": "ios-xe-17.6",
        "command_hierarchy": {...},
        "source_file": "path/to/pdf",
        "page_range": [start, end]
    }
}
```

**Embedding Model:** `all-MiniLM-L6-v2` (384 dimensions)

### 5. Three-Tier Validation (`src/validation/`)

#### Tier 1: Batfish (`batfish_validator.py`)
- **Technology:** Batfish static analysis engine
- **Input:** Generated configuration
- **Output:** Syntax errors, logical issues, policy violations
- **Speed:** ~100ms
- **Coverage:** ~80% of errors

#### Tier 2: Containerlab (`containerlab_validator.py`)
- **Technology:** Containerlab + Docker containers
- **Input:** Configuration + Topology
- **Output:** Protocol state, adjacencies, connectivity
- **Speed:** ~30 seconds
- **Coverage:** Protocol-level verification

#### Tier 3: GNS3 (`gns3_validator.py`)
- **Technology:** GNS3 + QEMU VMs
- **Input:** Full topology + Traffic patterns
- **Output:** Traffic flow, performance, edge cases
- **Speed:** 3-5 minutes
- **Coverage:** Production-like simulation

### 6. Configuration (`src/config.py`)

**Purpose:** Centralized settings management.

**Features:**
- Pydantic-based validation
- Environment variable loading
- WSL path handling
- LLM provider validation

**Settings Categories:**
- LLM Provider (groq/gemini)
- API Keys
- Vector DB paths
- Validation endpoints
- Application settings

## Data Flow

### 1. Intent Processing Flow

```
User Input
    │
    ▼
┌──────────────────┐
│  Intent Parser   │──▶ LLM (structured output)
└──────────────────┘
    │
    ▼
StructuredIntent (Pydantic)
    │
    ▼
ConfigGenerator
```

### 2. RAG Generation Flow

```
StructuredIntent
    │
    ├──▶ Query Formation (protocol + action + params)
    │
    ▼
VectorStore.retrieve()
    │
    ├──▶ Tier 1 Search (syntax, n=10)
    ├──▶ Tier 2 Search (patterns, n=5)
    │
    ▼
Context Assembly
    │
    ▼
Prompt Engineering
    │
    ▼
LLM Generation (with context)
    │
    ▼
Generated Config + Sources
```

### 3. Validation Flow

```
Generated Config
    │
    ├──▶ Tier 1: Batfish
    │      └─▶ Syntax OK?
    │         ├─▶ Yes ──▶ Continue
    │         └─▶ No  ──▶ Return Errors
    │
    ├──▶ Tier 2: Containerlab (optional)
    │      └─▶ Protocol Verification
    │
    └──▶ Tier 3: GNS3 (optional)
           └─▶ Full Simulation
```

## Technology Stack

### Core Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Language** | Python 3.10-3.11 | Core runtime |
| **LLM Framework** | LangChain | LLM orchestration |
| **LLM Providers** | Groq, Gemini | AI inference |
| **Vector DB** | ChromaDB | Document storage |
| **Embeddings** | Sentence Transformers | Text vectorization |
| **Validation** | Batfish, Containerlab, GNS3 | Network testing |
| **Web UI** | FastAPI + React | User interface |

### Dependencies

**Core:**
- `langchain` - LLM framework
- `langchain-groq` - Groq integration
- `langchain-google-genai` - Gemini integration
- `chromadb` - Vector database
- `sentence-transformers` - Embeddings

**Validation:**
- `pybatfish` - Batfish client
- Containerlab (binary)
- GNS3 server (package)

**Utilities:**
- `pydantic` - Data validation
- `python-dotenv` - Environment config
- `fastapi` - Web framework

## Module Dependencies

```
main.py
    ├──▶ parser/intent_parser
    │       └──▶ llm/LLMProvider
    │       └──▶ config/settings
    │
    ├──▶ rag/config_generator
    │       └──▶ llm/LLMProvider
    │       └──▶ rag/vector_store
    │       └──▶ config/settings
    │
    └──▶ config/settings
            └──▶ .env file
```

## Scalability Considerations

### Horizontal Scaling

**Vector Database:**
- ChromaDB supports server mode
- Can be replaced with Pinecone/Weaviate

**LLM Inference:**
- Multiple providers can be load-balanced
- Rate limiting handled per-provider

### Performance Optimizations

**Retrieval:**
- Pre-computed embeddings
- Cached vector search results
- Tiered retrieval (Tier 1 → Tier 2)

**Generation:**
- Streaming responses (optional)
- Response caching
- Batch processing for evaluation

## Security Architecture

### API Key Management
- Stored in environment variables
- Never committed to repository
- Validated at startup

### Input Validation
- Pydantic models for all inputs
- Intent sanitization
- Config syntax validation

### Container Security
- Rootless Podman support
- Docker security best practices
- Network isolation for validators

## Extension Points

### Adding New LLM Providers

1. Add to `src/llm/__init__.py`:
```python
@staticmethod
def _get_newprovider_llm(...):
    from langchain_newprovider import ChatNewProvider
    return ChatNewProvider(...)
```

2. Update `src/config.py` with API key setting

3. Add to `.env.example`

### Adding New Validators

1. Create `src/validation/new_validator.py`
2. Inherit from `BaseValidator`
3. Implement `validate()` method
4. Add to validation pipeline

### Adding New Vendors

1. Download vendor documentation
2. Add to `data/raw_docs/`
3. Update chunking logic
4. Add vendor-specific prompts

## Monitoring & Observability

### Logging
- Structured JSON logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Separate log files per component

### Metrics
- Generation time
- Retrieval accuracy
- Validation pass rates
- Hallucination scores

### Tracing
- Request ID propagation
- Component timing
- Error tracking

## Next Steps

- **[Usage Guide](USAGE.md)** - How to use the system
- **[API Reference](API.md)** - API documentation
- **[Configuration](CONFIGURATION.md)** - Configuration options

---

**Questions?** Refer to the [Troubleshooting Guide](TROUBLESHOOTING.md) or open an issue.
