# Justfile for RAG-NetTwin
# Modern command runner: https://github.com/casey/just

# Default: List available commands
default:
    @just --list

# Install all dependencies
install:
    uv sync

# Run the full test suite
test:
    uv run pytest tests/

# Run static analysis (linting and types)
lint:
    ruff check .
    mypy src/

# Build the Docker image
build:
    docker build -t rag-nettwin:latest .

# Run the interactive CLI
run:
    python main.py

# Run the FastAPI backend
api:
    uvicorn ui.backend.app:app --host 0.0.0.0 --port 8000

# Clean temporary files and caches
clean:
    rm -rf .pytest_cache .ruff_cache .mypy_cache
    find . -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf dist build *.egg-info
