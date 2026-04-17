"""
Configuration Module for RAG-NetTwin.

This module defines system-wide settings using Pydantic V2. It handles
environment variable loading, validation, and provides derived properties
for common paths. Settings can be overridden via .env file or environment
variables.

Key Features:
- Pydantic V2 BaseSettings for type-safe configuration
- Environment variable support via python-dotenv
- Automatic WSL detection for Windows/WSL interoperability
- Path normalization for cross-platform compatibility
- Provider-specific API key validation

Typical Usage:
    from config import settings

    # Access settings
    print(settings.groq_model)
    print(settings.chroma_persist_dir)

    # Use derived paths
    print(settings.data_dir)
    print(settings.raw_docs_dir)

Note:
    Run validation at module import to catch config issues early.
    Missing required keys will print warnings but not crash.
"""

import os
import platform
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from utils import is_wsl, fix_path, validate_provider_config

# Load environment variables into os.environ for external libraries
# LangChain, Groq, and other libraries read from os.environ
load_dotenv()


class Settings(BaseSettings):
    """
    System-wide settings for RAG-NetTwin using Pydantic V2.

    This class defines all configurable settings for the application.
    Settings can be provided via:
    1. Environment variables (highest priority)
    2. .env file in project root
    3. Default values (lowest priority)

    Attributes:
        is_wsl_detected: Whether running in WSL (Windows Subsystem for Linux).
        llm_provider: LLM provider to use ("groq", "gemini", or "llama_cpp").
        groq_api_key: API key for Groq LLM service.
        gemini_api_key: API key for Google Gemini service.
        chroma_persist_dir: Path to ChromaDB persistence directory.
        embedding_model_name: HuggingFace model name for embeddings.
        collection_name: Name of the ChromaDB collection.
        groq_model: Default Groq model to use.
        gemini_model: Default Gemini model to use.
        temperature: LLM temperature (0.0 = deterministic).
        gns3_host: GNS3 server hostname.
        gns3_port: GNS3 server port.
        batfish_host: Batfish service hostname.
        project_root: Derived path to project root directory.

    Properties:
        data_dir: Path to data directory (project_root/data).
        raw_docs_dir: Path to raw documentation directory.
        processed_chunks_dir: Path to processed chunks directory.
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
    chroma_persist_dir: str = "./data/chroma_db"
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    reranker_model_name: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    collection_name: str = "network_docs"

    # LLM Model Settings
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"
    gemini_model: str = "gemini-2.0-flash-lite-preview-02-05"
    temperature: float = 0.0

    # GNS3 Settings (Tier 3 validation)
    gns3_host: str = "localhost"
    gns3_port: int = 3080

    # Batfish Settings (Tier 1 validation)
    batfish_host: str = "127.0.0.1"

    # Paths (These are derived, not usually set via ENV)
    project_root: Path = Path(__file__).parent.parent.resolve()

    @property
    def data_dir(self) -> Path:
        """
        Get the data directory path.

        Returns:
            Path to the data directory (project_root/data).
        """
        return self.project_root / "data"

    @property
    def raw_docs_dir(self) -> Path:
        """
        Get the raw documentation directory path.

        Returns:
            Path to the raw docs directory (project_root/data/raw_docs).
        """
        return self.data_dir / "raw_docs"

    @property
    def processed_chunks_dir(self) -> Path:
        """
        Get the processed chunks directory path.

        Returns:
            Path to the processed chunks directory
            (project_root/data/processed_chunks).
        """
        return self.data_dir / "processed_chunks"

    @field_validator("chroma_persist_dir")
    @classmethod
    def fix_chroma_path(cls, v: str) -> str:
        """
        Fix ChromaDB path for cross-platform compatibility.

        This validator ensures the ChromaDB path is properly formatted
        for the current platform, handling WSL path conversions if needed.

        Args:
            v: The path string to validate/fix.

        Returns:
            Fixed path string suitable for the current platform.
        """
        return fix_path(v)

    def validate_config(self):
        """
        Perform manual validation of provider specific keys.

        This method validates that required API keys are present for
        the configured LLM provider. It checks:
        - Groq: requires GROQ_API_KEY
        - Gemini: requires GEMINI_API_KEY
        - LlamaCpp: requires LLAMA_CPP_MODEL_PATH

        Raises:
            ValueError: If required keys are missing for the provider.
        """
        config_dict = self.model_dump()
        validate_provider_config(self.llm_provider, config_dict)


# Global settings instance - singleton used throughout the application
settings = Settings()

# Run validation on import to catch config issues early
# This ensures we fail fast if required configuration is missing
try:
    settings.validate_config()
except ValueError as e:
    # Print a warning if config is incomplete instead of crashing
    # This allows the system to run in limited mode
    print(f"⚠️  Configuration Warning: {e}")
except Exception as e:
    print(f"⚠️  Unexpected error during config validation: {e}")
