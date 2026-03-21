import os
import platform
import subprocess
import re
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# --- Environment Utilities ---


def is_wsl() -> bool:
    """Detect if running inside WSL."""
    if platform.system() != "Linux":
        return False
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                return "microsoft" in f.read().lower()
    except (IOError, PermissionError):
        pass
    return False


def fix_path(path_str: str) -> str:
    """Convert Windows-style absolute paths to WSL-style if necessary."""
    if not path_str:
        return path_str
    if is_wsl() and len(path_str) > 2 and path_str[1] == ":" and path_str[2] == "\\":
        drive = path_str[0].lower()
        parts = path_str[3:].replace("\\", "/").split("/")
        return f"/mnt/{drive}/{'/'.join(parts)}"
    return path_str


# --- CLI Processing ---


def _is_cli_command(line: str) -> bool:
    """Check if a line looks like a valid network CLI command."""
    valid_starts = (
        "interface",
        "router",
        "ip ",
        "ipv6 ",
        "no ",
        "description",
        "set ",
        "configure",
        "policy-options",
        "routing-options",
        "protocols",
        "system",
        "snmp",
        "logging",
        "ntp",
        "user",
        "username",
        "access-list",
        "!",
        "exit",
        "quit",
        "commit",
        "apply",
        "firewall",
        "vlan",
        "spanning-tree",
        "area ",
        "network ",
        "neighbor ",
        "address-family",
        "route-map",
        "prefix-list",
        "hostname ",
        "banner ",
        "term ",
        "from ",
        "then ",
        "edit ",
        "family ",
        "ssh ",
        "lldp",
        "cdp",
        "class-map",
        "policy-map",
        "service-policy",
        "priority",
        "bandwidth",
        "fair-queue",
        "shape",
        "route-target",
        "extcommunity",
        "route-target",
        "address ",
        "mask ",
        "mask-src ",
        "src-packet",
        "distribute ",
        "redistribute",
    )
    lower = line.lower()
    return lower.startswith(valid_starts)


def clean_cli_prose(text: str) -> str:
    """
    Extracts valid network CLI commands from LLM output using simple string ops.
    No regex - only replace(), startswith(), in, strip()
    """
    # Handle empty config markers
    text = text.replace("<EOF>", "")
    text = text.replace("<end>", "")
    text = text.replace("[EOF]", "")

    # Remove markdown bold markers (**)
    text = text.replace("**", "")

    # Remove code block delimiters (```)
    text = text.replace("```", "\n")

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip markdown headers (# Header)
        if line.startswith("#"):
            continue

        # Skip markdown bullet points and separators
        if line in ("*", "-", "|", "---", "***"):
            continue

        # Skip lines that are clearly prose (no command-like content)
        prose_indicators = (
            "here is",
            "this command",
            "following",
            "example",
            "output:",
            "result:",
            "note:",
            "note that",
        )
        lower = line.lower()
        if any(lower.startswith(p) for p in prose_indicators):
            continue

        # Skip lines that are just numbers or special chars
        if line.replace(" ", "").replace("-", "").isdigit() or not any(
            c.isalpha() for c in line
        ):
            continue

        # Keep only CLI-like lines
        if _is_cli_command(line):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# --- Provider Validation ---


def validate_provider_config(provider: str, config: Dict[str, Any]):
    """Unified provider validation logic."""
    p = provider.lower()
    if p == "groq":
        if (
            not config.get("groq_api_key")
            or config.get("groq_api_key") == "your_api_key_here"
        ):
            raise ValueError("GROQ_API_KEY is missing or invalid.")
    elif p == "gemini":
        if (
            not config.get("gemini_api_key")
            or config.get("gemini_api_key") == "your_api_key_here"
        ):
            raise ValueError("GEMINI_API_KEY is missing or invalid.")
    elif p == "llamacpp":
        if not config.get("llama_cpp_model_path"):
            raise ValueError("LLAMA_CPP_MODEL_PATH is required for llamacpp.")
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")


# --- Research Metrics ---


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_est: float = 0.0


class TokenCounter:
    """Tracks token usage across the research lifecycle."""

    def __init__(self):
        self.session_usage: Dict[str, TokenUsage] = {}

    def add_usage(
        self, call_id: str, prompt: int, completion: int, model: str = "llama3"
    ):
        usage = TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
        # Simple heuristic cost estimation (per 1M tokens)
        rates = {"llama3": 0.05, "gemini": 0.10}
        rate = rates.get(model.lower(), 0.05)
        usage.cost_est = (usage.total_tokens / 1_000_000) * rate
        self.session_usage[call_id] = usage

    def get_total_usage(self) -> TokenUsage:
        total = TokenUsage()
        for u in self.session_usage.values():
            total.prompt_tokens += u.prompt_tokens
            total.completion_tokens += u.completion_tokens
            total.total_tokens += u.total_tokens
            total.cost_est += u.cost_est
        return total


# --- Logging ---


class LogEntry(BaseModel):
    """Strict schema for research and system logs"""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    level: str
    module: str
    message: str
    exception: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class JsonFormatter(logging.Formatter):
    """JSON log formatter using Pydantic for schema enforcement"""

    # Keys that contain sensitive data and should be redacted
    SENSITIVE_KEYS = {
        "api_key",
        "secret",
        "password",
        "token",
        "key",
        "credential",
        "auth",
    }

    def _scrub_dict(self, obj: Any) -> Any:
        """Recursively scrub sensitive data from dictionaries."""
        if isinstance(obj, dict):
            scrubbed = {}
            for k, v in obj.items():
                if any(sk in k.lower() for sk in self.SENSITIVE_KEYS):
                    scrubbed[k] = "[REDACTED]"
                else:
                    scrubbed[k] = self._scrub_dict(v)
            return scrubbed
        elif isinstance(obj, list):
            return [self._scrub_dict(item) for item in obj]
        elif isinstance(obj, str):
            # Check if string looks like an API key (long alphanumeric string)
            if len(obj) > 20 and all(c.isalnum() or c in ["_", "-"] for c in obj):
                # Likely an API key or token
                return "[REDACTED]"
        return obj

    def format(self, record):
        extra = getattr(record, "extra", {})
        scrubbed_extra = self._scrub_dict(extra)

        log_obj = LogEntry(
            level=record.levelname,
            module=record.module,
            message=record.getMessage(),
            extra=scrubbed_extra,
        )
        if record.exc_info:
            log_obj.exception = self.formatException(record.exc_info)

        return log_obj.model_dump_json()


def setup_logger(name: str, log_file: str = "rag_net.log", level=logging.INFO):
    """Configures a structured logger"""

    # Create logs directory
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Console Handler (Human readable, using rich if available)
    try:
        from rich.logging import RichHandler

        console_handler = RichHandler(rich_tracebacks=True, markup=True)
    except ImportError:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    logger.addHandler(console_handler)

    # File Handler (JSON structured)
    file_handler = logging.FileHandler(log_path / log_file)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    return logger
