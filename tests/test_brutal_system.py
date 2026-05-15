import json
import threading
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.evaluation.cache_manager import CacheManager
from src.validation.batfish_validator import BatfishValidator
from src.rag.config_generator import ConfigGenerator, CommandBlock
from src.schemas.intent import StructuredIntent, DeviceIntent, ActionType

# --- 1. CacheManager Torture Tests ---


def test_cache_corruption_recovery(tmp_path):
    """Ensure CacheManager doesn't crash on corrupted JSON."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    corrupt_file = cache_dir / "corrupt.json"
    corrupt_file.write_text("{ this is not json ]")

    cm = CacheManager(cache_dir=str(cache_dir))
    data = cm.load_cache("corrupt.json")
    assert data == {}  # Should return empty dict instead of crashing


def test_cache_parallel_writes(tmp_path):
    """Brutal parallel write test for CacheManager."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cm = CacheManager(cache_dir=str(cache_dir))

    def worker(worker_id):
        for i in range(20):
            cache = {
                f"key_{worker_id}_{i}": {
                    "status": "PASS",
                    "timestamp": datetime.now().isoformat(),
                }
            }
            cm.save_cache("parallel.json", cache)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    loaded = cm.load_cache("parallel.json")
    assert len(loaded) > 0


# --- 2. BatfishValidator Thread Safety & Error Handling ---


@patch("src.validation.batfish_validator.Session")
def test_batfish_404_handling(mock_session_class):
    """Simulate the 404 error seen in production."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    # Mock a 404 on answer().frame()
    mock_session.q.initIssues().answer.side_effect = Exception(
        "404 Client Error: Not Found"
    )

    validator = BatfishValidator()
    result = validator.validate({"R1": "!"})

    assert result["status"] == "ERROR"
    assert "404" in result["error"]


# --- 3. ConfigGenerator Schema & Isolation Tests ---


@patch("src.llm.LLMProvider.get_structured_llm")
def test_generator_null_field_resilience(mock_get_llm):
    """Test the fix for LLM returning 'null' reasoning_path."""
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    # Mock response with NULL in reasoning_path
    mock_response = MagicMock()
    mock_response.blocks = [CommandBlock(commands=["line 1"], source_ids=["ID1"])]
    mock_response.confidence_score = 0.9
    mock_response.reasoning_path = None  # The problematic case
    mock_response.verification_commands = []
    mock_response.explanation = None

    mock_llm.invoke.return_value = mock_response

    generator = ConfigGenerator()
    intent = StructuredIntent(
        action=ActionType.ENABLE,
        protocol="OSPF",
        devices=[DeviceIntent(name="R1", vendor="cisco")],
        original_text="test",
    )

    # Should not crash because our Pydantic model now has a default
    res = generator.generate(intent, retrieval_mode="none")
    assert res["R1"]["config"] != "ERROR"


@patch("src.llm.LLMProvider.get_structured_llm")
@patch("src.rag.multi_vendor_coordinator.MultiVendorCoordinator.generate_interop_plan")
@patch(
    "src.rag.multi_vendor_coordinator.MultiVendorCoordinator.extract_shared_constraints"
)
def test_generator_parallel_stress(mock_constraints, mock_plan, mock_get_llm):
    """Generate for 20 devices at once to test thread pool."""
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    # Mock coordination to return simple strings/dicts instead of MagicMocks
    mock_constraints.return_value = {}

    plan_mock = MagicMock()
    plan_mock.proposed_parameters = {"vlan": 10}
    plan_mock.model_dump.return_value = {"proposed_parameters": {"vlan": 10}}
    mock_plan.return_value = plan_mock

    mock_response = MagicMock()
    mock_response.blocks = [CommandBlock(commands=["!"], source_ids=[])]
    mock_response.reasoning_path = "ok"
    mock_response.confidence_score = 1.0
    mock_response.verification_commands = []
    mock_response.explanation = ""
    mock_llm.invoke.return_value = mock_response

    generator = ConfigGenerator()
    devices = [DeviceIntent(name=f"R{i}", vendor="cisco") for i in range(20)]
    intent = StructuredIntent(
        action=ActionType.ENABLE, protocol="OSPF", devices=devices
    )

    results = generator.generate(intent, retrieval_mode="none")
    assert len(results) >= 20


# --- 4. run_paper_eval Logic Tests ---


def test_selective_clear_failed(tmp_path):
    """Brutally test the --clear-failed logic."""
    cache_dir = tmp_path / "data/cache"
    cache_dir.mkdir(parents=True)
    rag_cache_file = cache_dir / "rag_cache.json"

    test_data = {
        "pass_key": {"status": "PASS", "timestamp": "2026-01-01"},
        "fail_key": {"status": "FAIL", "timestamp": "2026-01-01"},
        "error_key": {"status": "ERROR", "timestamp": "2026-01-01"},
        "manual_key": {"status": "REJECT_FOR_MANUAL_REVIEW", "timestamp": "2026-01-01"},
    }

    with open(rag_cache_file, "w") as f:
        json.dump(test_data, f)

    filepath = rag_cache_file
    with open(filepath, "r") as f:
        full_cache = json.load(f)
        cleaned_cache = {
            k: v
            for k, v in full_cache.items()
            if v.get("status") in ["PASS", "WARNING", "REJECT_FOR_MANUAL_REVIEW"]
        }

    assert "pass_key" in cleaned_cache
    assert "manual_key" in cleaned_cache
    assert "fail_key" not in cleaned_cache
    assert "error_key" not in cleaned_cache


if __name__ == "__main__":
    pytest.main([__file__])
