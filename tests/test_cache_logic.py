import os
import shutil
from datetime import datetime, timedelta
from src.evaluation.cache_manager import CacheManager


def test_status_based_ttl():
    cache_dir = "data/test_cache"
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

    cm = CacheManager(cache_dir=cache_dir)
    cache = {}

    # 1. PASS entry (should last 30 days)
    # Set to 15 days ago -> should NOT be expired
    pass_time = (datetime.now() - timedelta(days=15)).isoformat()
    cm.set(cache, "pass_key", {"status": "PASS"}, mode="tiered")
    cache["pass_key"]["timestamp"] = pass_time

    # 2. FAIL entry (should last 1 hour)
    # Set to 2 hours ago -> should BE expired
    fail_time = (datetime.now() - timedelta(hours=2)).isoformat()
    cm.set(cache, "fail_key", {"status": "FAIL"}, mode="tiered")
    cache["fail_key"]["timestamp"] = fail_time

    # 3. Recent FAIL entry (should NOT be expired)
    recent_fail_time = (datetime.now() - timedelta(minutes=30)).isoformat()
    cm.set(cache, "recent_fail_key", {"status": "FAIL"}, mode="tiered")
    cache["recent_fail_key"]["timestamp"] = recent_fail_time

    cm.save_cache("test.json", cache)

    # Reload
    loaded = cm.load_cache("test.json")

    assert "pass_key" in loaded, "PASS entry should NOT be expired after 15 days"
    assert "fail_key" not in loaded, "FAIL entry SHOULD be expired after 2 hours"
    assert (
        "recent_fail_key" in loaded
    ), "Recent FAIL entry should NOT be expired after 30 mins"

    print("✅ Status-based TTL verification passed!")
    shutil.rmtree(cache_dir)


if __name__ == "__main__":
    test_status_based_ttl()
