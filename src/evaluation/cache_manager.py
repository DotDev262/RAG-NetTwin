import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from src.utils import setup_logger

logger = setup_logger("CacheManager")

CACHE_EXPIRY_DAYS = 7


class CacheManager:
    """
    Manages evaluation results caching on disk.
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def load_cache(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.cache_dir, filename)
        if not os.path.exists(filepath):
            return {}

        try:
            with open(filepath, "r") as f:
                cache = json.load(f)

            cutoff = datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS)
            filtered = {}
            for key, value in cache.items():
                if isinstance(value, dict) and value.get("status") == "ERROR":
                    continue

                ts = value.get("timestamp", "") if isinstance(value, dict) else ""
                if ts:
                    try:
                        entry_time = datetime.fromisoformat(ts)
                        if entry_time > cutoff:
                            filtered[key] = value
                    except (ValueError, TypeError):
                        # Skip entries with invalid timestamps
                        pass
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
        ts = value.get("timestamp", "")
        if ts:
            try:
                entry_time = datetime.fromisoformat(ts)
                if entry_time < datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS):
                    return None
            except Exception:
                pass
        return value

    def set(self, cache: Dict, key: str, value: Any, mode: Optional[str] = None):
        cache[key] = {
            **value,
            "timestamp": datetime.now().isoformat(),
            "mode_tag": mode,
        }
