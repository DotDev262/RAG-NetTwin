"""
Utility Functions Module for RAG-NetTwin.

This module provides shared utility functions used across the application,
including environment detection, CLI processing, provider validation,
token tracking, and logging configuration.

Key Features:
- WSL detection for cross-platform path handling
- CLI command extraction from LLM output
- API provider configuration validation
- Token usage tracking for cost estimation
- Structured JSON logging with sensitive data redaction

Typical Usage:
    from utils import setup_logger, clean_cli_prose, is_wsl

    # Setup logging
    logger = setup_logger("ModuleName")
    logger.info("Starting process")

    # Clean LLM output
    cleaned = clean_cli_prose(llm_output)

    # Check environment
    if is_wsl():
        print("Running in WSL")
"""

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
    """
    Detect if running inside WSL (Windows Subsystem for Linux).

    This function checks if the current process is running under WSL,
    which affects how file paths should be handled (Windows-style vs
    Unix-style paths).

    Returns:
        True if running in WSL, False otherwise.

    Example:
        >>> is_wsl()
        True  # If running in WSL on Windows
        False  # If running on native Linux or macOS
    """
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
    """
    Convert Windows-style absolute paths to WSL-style if necessary.

    This function transforms Windows paths (e.g., "C:\\Users\\...")
    to WSL paths (e.g., "/mnt/c/Users/...") when running in WSL.
    This is necessary because tools like ChromaDB and Docker expect
    Unix-style paths even when running in WSL.

    Args:
        path_str: A file system path that may be in Windows format.

    Returns:
        The path converted to WSL format if in WSL and path is Windows-style,
        otherwise returns the original path unchanged.

    Example:
        >>> fix_path("D:\\data\\chroma_db")
        '/mnt/d/data/chroma_db'  # If in WSL
        'D:\\data\\chroma_db'    # If not in WSL
    """
    if not path_str:
        return path_str
    # Check for Windows-style path (e.g., "C:\...")
    if is_wsl() and len(path_str) > 2 and path_str[1] == ":" and path_str[2] == "\\":
        drive = path_str[0].lower()
        parts = path_str[3:].replace("\\", "/").split("/")
        return f"/mnt/{drive}/{'/'.join(parts)}"
    return path_str


# --- CLI Processing ---


def _is_cli_command(line: str) -> bool:
    """
    Check if a line looks like a valid network CLI command.

    This is a helper function used by clean_cli_prose() to identify
    lines that are actual CLI commands versus explanatory text or
    prose. It checks against a list of known command prefixes.

    Args:
        line: A single line of text to check.

    Returns:
        True if the line appears to be a valid CLI command, False otherwise.

    Note:
        This function uses startswith() checks for efficiency rather than
        full parsing. It may occasionally include non-command lines or
        exclude valid but unusual commands.
    """
    # List of command prefixes that indicate valid CLI commands
    # Covers Cisco IOS, Juniper JunOS, and common network commands
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
        "!",  # Cisco comment character
        "exit",
        "quit",
        "commit",  # Juniper commit
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
        "from ",  # Juniper policy terms
        "then ",  # Juniper policy terms
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
    Extract valid network CLI commands from LLM output.

    This function processes text from an LLM response and extracts
    only the valid CLI commands, filtering out:
    - Markdown formatting (**bold**, ```code blocks```)
    - Prose and explanations
    - Empty config markers (<EOF>, <end>)
    - Markdown headers and bullet points

    The function uses simple string operations (replace, startswith, in)
    rather than regex for efficiency and maintainability.

    Args:
        text: Raw output from LLM that may contain CLI commands mixed
            with prose explanations.

    Returns:
        A string containing only the extracted CLI commands, one per line.
        Returns empty string if no valid commands found.

    Example:
        >>> output = '''
        ... Here is the configuration:
        ... !
        ... interface GigabitEthernet0/1
        ...  ip address 192.168.1.1 255.255.255.0
        ... !
        ... '''
        >>> clean_cli_prose(output)
        'interface GigabitEthernet0/1\\nip address 192.168.1.1 255.255.255.0'
    """
    # Handle empty config markers that LLMs sometimes add
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
        # These often appear as list numbers or separators
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
    """
    Unified provider validation logic.

    This function validates that required configuration keys are present
    for the specified LLM provider. It checks for API keys and other
    required settings based on the provider type.

    Args:
        provider: The LLM provider name (e.g., "groq", "gemini", "llamacpp").
        config: Configuration dictionary to validate.

    Raises:
        ValueError: If required keys are missing or invalid.

    Note:
        This function is called during config validation at startup.
        It should fail fast to alert users to configuration issues.
    """
    p = provider.lower()
    if p == "groq":
        # Groq requires a valid API key
        if (
            not config.get("groq_api_key")
            or config.get("groq_api_key") == "your_api_key_here"
        ):
            raise ValueError("GROQ_API_KEY is missing or invalid.")
    elif p == "gemini":
        # Gemini requires a valid API key
        if (
            not config.get("gemini_api_key")
            or config.get("gemini_api_key") == "your_api_key_here"
        ):
            raise ValueError("GEMINI_API_KEY is missing or invalid.")
    elif p == "llamacpp":
        # Local LLM requires a model file path
        if not config.get("llama_cpp_model_path"):
            raise ValueError("LLAMA_CPP_MODEL_PATH is required for llamacpp.")
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")


# --- Research Metrics ---


class TokenUsage(BaseModel):
    """
    Pydantic model for tracking token usage.

    This model records the number of tokens used in an LLM API call
    and provides a field for cost estimation.

    Attributes:
        prompt_tokens: Number of tokens in the input prompt.
        completion_tokens: Number of tokens in the LLM response.
        total_tokens: Sum of prompt and completion tokens.
        cost_est: Estimated cost in USD based on token count.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_est: float = 0.0


class TokenCounter:
    """
    Tracks token usage across the research lifecycle.

    This class accumulates token usage data from multiple LLM calls
    and provides totals for cost estimation and monitoring.

    Attributes:
        session_usage: Dictionary mapping call IDs to TokenUsage objects.

    Example:
        >>> counter = TokenCounter()
        >>> counter.add_usage("call_001", 1000, 500, "llama3")
        >>> counter.add_usage("call_002", 1500, 750, "llama3")
        >>> total = counter.get_total_usage()
        >>> print(f"Total tokens: {total.total_tokens}")
    """

    def __init__(self):
        self.session_usage: Dict[str, TokenUsage] = {}

    def add_usage(
        self, call_id: str, prompt: int, completion: int, model: str = "llama3"
    ):
        """
        Add token usage for a single LLM call.

        Args:
            call_id: Unique identifier for this call (e.g., "parse_001").
            prompt: Number of tokens in the prompt.
            completion: Number of tokens in the completion.
            model: Model name for rate lookup (default: "llama3").
        """
        usage = TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
        # Simple heuristic cost estimation (per 1M tokens)
        # Rates are approximate and should be updated with current pricing
        rates = {"llama3": 0.05, "gemini": 0.10}
        rate = rates.get(model.lower(), 0.05)
        usage.cost_est = (usage.total_tokens / 1_000_000) * rate
        self.session_usage[call_id] = usage

    def get_total_usage(self) -> TokenUsage:
        """
        Get total token usage across all recorded calls.

        Returns:
            TokenUsage object with aggregated totals.
        """
        total = TokenUsage()
        for u in self.session_usage.values():
            total.prompt_tokens += u.prompt_tokens
            total.completion_tokens += u.completion_tokens
            total.total_tokens += u.total_tokens
            total.cost_est += u.cost_est
        return total


# --- Logging ---


class LogEntry(BaseModel):
    """
    Strict schema for research and system logs.

    This model defines the structure of log entries used throughout
    the application. It ensures consistent log format and enables
    structured log processing.

    Attributes:
        timestamp: ISO format timestamp of the log entry.
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        module: Name of the module generating the log.
        message: The log message.
        exception: Optional exception traceback if applicable.
        extra: Additional context data as key-value pairs.
    """

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    level: str
    module: str
    message: str
    exception: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter using Pydantic for schema enforcement.

    This formatter outputs log entries as JSON, making them easy to
    parse and analyze with log aggregation tools. It automatically
    redacts sensitive information like API keys and passwords.

    Attributes:
        SENSITIVE_KEYS: Set of keys that contain sensitive data.
    """

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
        """
        Recursively scrub sensitive data from dictionaries.

        This method traverses a dictionary (or nested structure) and
        redacts values that match sensitive key patterns or look like
        API keys (long alphanumeric strings).

        Args:
            obj: Object to scrub (dict, list, or string).

        Returns:
            The same structure with sensitive data redacted.
        """
        if isinstance(obj, dict):
            scrubbed = {}
            for k, v in obj.items():
                # Redact if key matches sensitive patterns
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
        """
        Format a log record as JSON with sensitive data redacted.

        Args:
            record: Python log record to format.

        Returns:
            JSON string representation of the log entry.
        """
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


def calculate_mrr(relevant_id: str, retrieved_ids: List[str]) -> float:
    """
    Calculates Mean Reciprocal Rank (MRR).
    (Recommendation 3 Elite)
    """
    try:
        rank = retrieved_ids.index(relevant_id) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0


def calculate_ndcg(relevant_id: str, retrieved_ids: List[str]) -> float:
    """
    Calculates Normalized Discounted Cumulative Gain (NDCG) for a single relevant item.
    (Recommendation 3 Elite)
    """
    import numpy as np
    try:
        rank = retrieved_ids.index(relevant_id) + 1
        # DCG = rel / log2(rank + 1). Here rel is binary (1 for the ground truth)
        dcg = 1.0 / np.log2(rank + 1)
        # IDCG is always 1.0 / log2(1 + 1) = 1.0 for a single relevant item
        idcg = 1.0
        return dcg / idcg
    except ValueError:
        return 0.0


def setup_logger(name: str, log_file: str = "rag_net.log", level=logging.INFO):
    """
    Configures a structured logger.
    """
    # Create logs directory
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Console Handler
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


def generate_audit_report(
    intent: Any, 
    configs: Dict[str, Any], 
    output_dir: str = "results/audits"
) -> str:
    """
    Generates a structured Markdown 'Grounding Audit Report' for an intent.
    (Recommendation 5)
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_text = re.sub(r'[^\w\s-]', '', intent.original_text[:30]).strip().replace(" ", "_")
    filename = f"audit_{timestamp}_{safe_text}.md"
    filepath = os.path.join(output_dir, filename)

    report = [
        f"# Grounding Audit Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Original Intent:** {intent.original_text}",
        f"\n## 1. Structured Intent Analysis",
        f"- **Protocol:** {intent.protocol}",
        f"- **Action:** {intent.action}",
        f"- **Parameters:** `{json.dumps(intent.parameters)}`",
        f"\n## 2. Generation & Grounding Details"
    ]

    for device_name, data in configs.items():
        if device_name.startswith("_"):
            continue
        report.append(f"### Device: {device_name}")
        report.append(f"#### Reasoning Path\n{data.get('reasoning', 'N/A')}")
        
        report.append(f"#### Retrieved Documentation Snippets")
        # In a real scenario, we'd pass the actual texts here. 
        # For now, we list the source IDs.
        sources = data.get('retrieved_sources', [])
        if sources:
            report.append(f"- **Sources used:** {', '.join(sources)}")
        else:
            report.append("- *No documentation retrieved (Lite path used or no matches).*")

        report.append(f"#### Generated Configuration\n```\n{data.get('config', 'N/A')}\n```")
        
        if "validation" in data:
            val = data["validation"]
            report.append(f"#### Validation Results (Tier 1)")
            report.append(f"- **Status:** {val.get('status')}")
            if val.get("issues"):
                report.append(f"- **Issues found:**")
                for issue in val["issues"]:
                    report.append(f"  - [{issue['type']}] {issue['details']}")

    with open(filepath, "w") as f:
        f.write("\n".join(report))
    
    return filepath
