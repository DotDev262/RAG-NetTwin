"""
Configuration Module for RAG-NetTwin.

This module defines system-wide settings using Pydantic V2. It handles
environment variable loading, validation, and provides derived properties
for common paths. Settings can be overridden via .env file or environment
variables.
"""

from __future__ import annotations
import os
from pathlib import Path

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from src.utils import is_wsl, fix_path

# Load environment variables into os.environ for external libraries
load_dotenv()


class Settings(BaseSettings):
    """
    System-wide settings for RAG-NetTwin using Pydantic V2.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Environment Detection
    is_wsl_detected: bool = Field(default_factory=is_wsl)

    # LLM Provider Settings
    llm_provider: str = "groq"

    # LlamaCpp Settings (for local LLM)
    llama_cpp_model_path: str = ""
    llama_cpp_n_ctx: int = 4096
    llama_cpp_n_gpu_layers: int = -1

    # API Keys (empty by default, must be set via env)
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Vector DB Settings
    chroma_persist_dir: str = Field(
        default="./data/chroma_db", validation_alias="chroma_db_path"
    )
    embedding_model_name: str = os.getenv(
        "EMBEDDING_MODEL", "ibm-granite/granite-embedding-311m-multilingual-r2"
    )
    reranker_model_name: str = os.getenv(
        "RERANKER_MODEL", "Alibaba-NLP/gte-reranker-modernbert-base"
    )
    collection_name: str = "network_docs"

    # LLM Model Settings
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"
    gemini_model: str = "gemini-2.0-flash-lite-preview-02-05"
    temperature: float = 0.0
    llm_max_retries: int = 10
    enable_self_correction: bool = False
    use_live_llm: bool = False

    # GNS3 Settings (Tier 3 validation)
    gns3_host: str = "localhost"
    gns3_port: int = 3080

    # Batfish Settings (Tier 1 validation)
    batfish_host: str = "127.0.0.1"

    # Paths (These are derived, not usually set via ENV)
    project_root: Path = Path(__file__).parent.parent.resolve()

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_docs_dir(self) -> Path:
        return self.data_dir / "raw_docs"

    @property
    def processed_chunks_dir(self) -> Path:
        return self.data_dir / "processed_chunks"

    @field_validator("chroma_persist_dir")
    @classmethod
    def fix_chroma_path(cls, v: str) -> str:
        return fix_path(v)

    @model_validator(mode="after")
    def validate_llm_provider(self) -> Self:
        """
        Ensure required keys are present for the selected LLM provider.
        """
        provider = self.llm_provider.lower()
        if provider == "groq":
            if not self.groq_api_key or self.groq_api_key == "your_api_key_here":
                raise ValueError("GROQ_API_KEY is missing or invalid.")
        elif provider == "gemini":
            if not self.gemini_api_key or self.gemini_api_key == "your_api_key_here":
                raise ValueError("GEMINI_API_KEY is missing or invalid.")
        elif provider == "llamacpp":
            if not self.llama_cpp_model_path:
                raise ValueError("LLAMA_CPP_MODEL_PATH is required for llamacpp.")
        elif provider == "ollama":
            # Ollama runs locally, no key verification required
            pass
        else:
            raise ValueError(f"Unsupported LLM provider: '{self.llm_provider}'")
        return self


# Global settings instance
try:
    settings = Settings()
except Exception as e:
    # Print a warning and use construct to avoid crashing non-LLM scripts
    print(f"❌ Configuration Error: {e}")
    settings = Settings.model_construct()
