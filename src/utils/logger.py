import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """
    Strict schema for research and system logs.
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
    """

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
            if len(obj) > 20 and all(c.isalnum() or c in ["_", "-"] for c in obj):
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
    """
    Configures a structured logger.
    """
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        logger.handlers.clear()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(console_handler)
    file_handler = logging.FileHandler(log_path / log_file)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    logging.getLogger("ciscoconfparse").setLevel(logging.WARNING)
    logging.getLogger("pybatfish").setLevel(logging.WARNING)
    try:
        from loguru import logger as loguru_logger

        loguru_logger.remove()
        loguru_logger.add(
            sys.stderr,
            filter=lambda record: "ciscoconfparse" not in record["name"]
            or record["level"].no >= 40,
        )
    except ImportError:
        pass
    return logger
