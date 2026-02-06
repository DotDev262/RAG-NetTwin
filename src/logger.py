import logging
import sys
import json
from pathlib import Path
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """JSON log formatter"""
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def setup_logger(name: str, log_file: str = "rag_net.log", level=logging.INFO):
    """Configures a structured logger"""
    
    # Create logs directory
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
        
    # Console Handler (Human readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # File Handler (JSON structured)
    file_handler = logging.FileHandler(log_path / log_file)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    return logger
