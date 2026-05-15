import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from src.utils import setup_logger

logger = setup_logger("CacheManager")

SUCCESS_TTL_DAYS = 30
FAILURE_TTL_HOURS = 1


class CacheManager:
    """
    Manages evaluation results caching on disk.
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _is_expired(self, value: Dict[str, Any]) -> bool:
        """
        Check if a cache entry is expired based on its status.
        """
        if not isinstance(value, dict):
            return True

        ts = value.get("timestamp", "")
        if not ts:
            return True

        try:
            entry_time = datetime.fromisoformat(ts)
            status = value.get("status", "ERROR")

            # Determine TTL based on status
            if status in ["PASS", "WARNING", "REJECT_FOR_MANUAL_REVIEW"]:
                cutoff = datetime.now() - timedelta(days=SUCCESS_TTL_DAYS)
            else:
                cutoff = datetime.now() - timedelta(hours=FAILURE_TTL_HOURS)

            return entry_time < cutoff
        except (ValueError, TypeError):
            return True

    def load_cache(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.cache_dir, filename)
        if not os.path.exists(filepath):
            return {}

        try:
            with open(filepath, "r") as f:
                cache = json.load(f)

            filtered = {}
            for key, value in cache.items():
                if not self._is_expired(value):
                    filtered[key] = value
            return filtered
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load cache {filepath}: {e}")
            return {}

    def save_cache(self, filename: str, cache: Dict[str, Any]):
        if not cache:
            return

        filepath = os.path.join(self.cache_dir, filename)
        try:
            disk_cache = {}
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        disk_cache = json.load(f)
                except Exception:
                    pass

            disk_cache.update(cache)
            with open(filepath, "w") as f:
                json.dump(disk_cache, f, indent=2)
            logger.info(f"Saved cache to {filepath} ({len(disk_cache)} items)")
        except Exception as e:
            logger.warning(f"Failed to save cache {filepath}: {e}")

    def get(self, cache: Dict, key: str) -> Optional[Any]:
        if key not in cache:
            return None

        value = cache[key]
        if self._is_expired(value):
            return None
        return value

    def set(self, cache: Dict, key: str, value: Any, mode: Optional[str] = None):
        cache[key] = {
            **value,
            "timestamp": datetime.now().isoformat(),
            "mode_tag": mode,
        }
