import os
import platform
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from utils import is_wsl, fix_path, validate_provider_config

# Load environment variables into os.environ for external libraries (LangChain, Groq, etc.)
load_dotenv()


class Settings(BaseSettings):
    """System-wide settings for RAG-NetTwin using Pydantic V2"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Environment Detection
    is_wsl_detected: bool = Field(default_factory=is_wsl)

    # LLM Provider Settings
    llm_provider: str = "groq"

    # LlamaCpp Settings
    llama_cpp_model_path: str = ""
    llama_cpp_n_ctx: int = 4096
    llama_cpp_n_gpu_layers: int = -1

    # API Keys
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Vector DB
    chroma_persist_dir: str = "./data/chroma_db"
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    collection_name: str = "network_docs"

    # LLM Model Settings
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"
    gemini_model: str = "gemini-2.0-flash-lite-preview-02-05"
    temperature: float = 0.0

    # GNS3 Settings
    gns3_host: str = "localhost"
    gns3_port: int = 3080

    # Batfish Settings
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

    def validate_config(self):
        """Perform manual validation of provider specific keys."""
        config_dict = self.model_dump()
        validate_provider_config(self.llm_provider, config_dict)


# Global settings instance
settings = Settings()

# Run validation on import
try:
    settings.validate_config()
except ValueError as e:
    # Print a warning if config is incomplete instead of crashing
    print(f"⚠️  Configuration Warning: {e}")
except Exception as e:
    print(f"⚠️  Unexpected error during config validation: {e}")
