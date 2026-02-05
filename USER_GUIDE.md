# RAG-NetTwin: User Guide

## Overview
**RAG-NetTwin** is a Hallucination-Mitigated Intent-Based Networking system. It uses Retrieval-Augmented Generation (RAG) to convert natural language network intents into verified CLI configurations, ensuring syntax accuracy by retrieving commands from official vendor documentation.

## 1. Setup & Installation

### Prerequisites
- **Python 3.10+** (managed via `uv`)
- **Docker** (for Batfish validation)
- **Groq API Key** (for LLM inference)

### Installation
1. **Clone the repository**:
   ```bash
   git clone <repo_url>
   cd rag-nettwin
   ```

2. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync
   # Or manual pip
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```bash
   GROQ_API_KEY=gsk_...  # Your key from console.groq.com
   BATFISH_HOST=localhost
   BATFISH_PORT=9997
   CHROMA_PERSIST_DIR=./data/chroma_db
   ```

## 2. Data Ingestion Pipeline

Before generating configurations, you must ingest the vendor documentation.

1. **Place PDFs** in `data/raw_docs/`.
2. **Update Index**: Ensure `data/doc_index.json` references your files.
3. **Run Pipeline**:
   ```bash
   uv run python src/data_processing/pipeline.py
   ```
   *Expected Output*: "Added X chunks to vector database"

## 3. Using the System

### Interactive Dashboard
Run the FastAPI backend to use the web dashboard:

```bash
uv run python ui/backend/main.py
```
Then open `ui/frontend/index.html` in your browser.

### Evaluation Suite
Compare RAG-NetTwin against a vanilla LLM baseline:

```bash
uv run python src/evaluation/evaluator.py
```
This generates `results/benchmark_report.json` with hallucination scores.

### Validation (Batfish)
To enable Tier 1 validation (Static Analysis):

1. **Start Batfish**:
   ```bash
   docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
   ```

2. **Run Validation Test**:
   ```bash
   uv run python tests/test_validation.py
   ```
   *Note*: The system will automatically skip validation if Batfish is not reachable.

### Validation (Tier 3: GNS3)
To enable Full Emulation:

1. **Start GNS3 Server**:
   Ensure the GNS3 server is running locally on port 3080.
   
2. **Configure Environment** (Optional):
   Update `.env` if your GNS3 server is on a different host/port:
   ```bash
   GNS3_HOST=localhost
   GNS3_PORT=3080
   ```

3. **Run Validation**:
   The system automatically attempts to connect to GNS3. If connected, it will create a project and topology based on the intent.

## 4. Project Structure
- `src/`: Core engine logic (Parser, RAG, Validation).
- `ui/frontend/`: HTML/JS dashboard assets.
- `ui/backend/`: FastAPI backend implementation.
- `data/`: Storage for docs, chunks, and vector DB.

## Troubleshooting
- **Missing API Key**: Check `.env` and restart the script.
- **Batfish Connection Refused**: Ensure Docker container is running (`docker ps`).
- **Import Errors**: Run `uv sync` to ensure all dependencies are installed.
