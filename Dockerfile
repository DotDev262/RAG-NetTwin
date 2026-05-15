# Multi-stage Dockerfile for RAG-NetTwin
FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/
COPY main.py ./
COPY ui/ ./ui/
COPY GEMINI.md ./

# Final stage: Production image
FROM python:3.11-slim AS production

WORKDIR /app

# Copy the virtual environment and code from base
COPY --from=base /app /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV LOG_LEVEL=INFO

# Expose API port
EXPOSE 8000

# Default command: Run the API
CMD ["uvicorn", "ui.backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
