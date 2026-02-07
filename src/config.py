import os
import platform
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


def is_wsl():
    """Detect if running inside WSL."""
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except:
        return False


def get_wsl_host_ip():
    """Get the IP address of the Windows host from WSL."""
    try:
        result = subprocess.run(["ip", "route"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "default via" in line:
                return line.split()[2]
    except:
        pass
    return "localhost"


def fix_path(path_str: str) -> str:
    """Convert Windows-style absolute paths to WSL-style if necessary."""
    if not path_str:
        return path_str
    if is_wsl() and len(path_str) > 2 and path_str[1] == ":" and path_str[2] == "\\":
        drive = path_str[0].lower()
        parts = path_str[3:].replace("\\", "/").split("/")
        return f"/mnt/{drive}/{'/'.join(parts)}"
    return path_str


class Settings(BaseModel):
    """System-wide settings for RAG-NetTwin"""

    # Environment Detection
    is_wsl: bool = Field(default_factory=is_wsl)

    # LLM Provider Settings
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq"))

    # API Keys
    groq_api_key: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))

    # Vector DB
    chroma_persist_dir: str = Field(
        default_factory=lambda: fix_path(
            os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        )
    )
    embedding_model_name: str = "all-MiniLM-L6-v2"
    collection_name: str = "cisco_commands"

    # LLM Model Settings (Provider-specific)
    groq_model: str = Field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    )
    temperature: float = 0.0

    # GNS3 Settings
    gns3_host: str = Field(default_factory=lambda: os.getenv("GNS3_HOST", "localhost"))
    gns3_port: int = Field(default_factory=lambda: int(os.getenv("GNS3_PORT", 3080)))

    # File Paths
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    raw_docs_dir: Path = data_dir / "raw_docs"
    processed_chunks_dir: Path = data_dir / "processed_chunks"

    # Validation
    batfish_host: str = Field(
        default_factory=lambda: os.getenv("BATFISH_HOST", "localhost")
    )

    class Config:
        case_sensitive = False


# Global settings instance
settings = Settings()


def validate_llm_config():
    """Validate LLM provider configuration at startup."""
    provider = settings.llm_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key or settings.groq_api_key == "your_api_key_here":
            raise ValueError(
                "GROQ_API_KEY is required when using provider 'groq'. "
                "Please set GROQ_API_KEY in your .env file."
            )
    elif provider == "gemini":
        if (
            not settings.gemini_api_key
            or settings.gemini_api_key == "your_api_key_here"
        ):
            raise ValueError(
                "GEMINI_API_KEY is required when using provider 'gemini'. "
                "Please set GEMINI_API_KEY in your .env file."
            )
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. Supported providers: groq, gemini"
        )


# Validate LLM configuration on module import
validate_llm_config()
