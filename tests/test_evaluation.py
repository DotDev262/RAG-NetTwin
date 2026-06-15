import pytest
import warnings
from typing import Dict, Any

# Suppress telnetlib deprecation warning (slated for removal in Python 3.13)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="telnetlib")
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning:telnetlib")

# Add src to path for imports
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.append(str(Path(__file__).parent.parent))
# noqa: E402
from src.schemas.intent import StructuredIntent  # noqa: E402
from run_paper_eval import PaperQualityEvaluator  # noqa: E402


class MockEvaluator(PaperQualityEvaluator):
    def __init__(self) -> None:
        # Skip the heavy initialization
        self.vanilla_llm = None
        self.rag_cache: Dict[str, Any] = {}
        self.vanilla_cache: Dict[str, Any] = {}

        # Initialize sub-components for testing
        from src.evaluation.cache_manager import CacheManager
        from src.evaluation.cfr_checker import CFRChecker
        from src.evaluation.stats_reporter import StatsReporter

        self.cache_manager = CacheManager()
        self.cfr_checker = CFRChecker()
        self.stats_reporter = StatsReporter()

    def _junos_config_to_dict(self, config: str) -> Dict[str, Any]:
        return self.cfr_checker._junos_config_to_dict(config)

    def _check_cfr(self, intent: StructuredIntent, config: str) -> bool:
        return self.cfr_checker.check(intent, config)


@pytest.fixture
def evaluator():
    return MockEvaluator()


def test_junos_config_to_dict(evaluator):
    config = """
    set interfaces ge-0/0/0 unit 0 family inet address 10.1.1.1/24
    set protocols ospf area 0.0.0.0 interface ge-0/0/0.0
    """
    tree = evaluator._junos_config_to_dict(config)

    assert "interfaces" in tree
    assert "ge-0/0/0" in tree["interfaces"]
    assert "address" in tree["interfaces"]["ge-0/0/0"]["unit"]["0"]["family"]["inet"]
    assert (
        "10.1.1.1/24"
        in tree["interfaces"]["ge-0/0/0"]["unit"]["0"]["family"]["inet"]["address"]
    )


def test_check_cfr_basic_pass(evaluator):
    intent = StructuredIntent(
        original_text="Configure OSPF area 0",
        parameters={"area": "0"},
    )
    config = "router ospf 1\n network 0.0.0.0 255.255.255.255 area 0"

    # CFR returns False if NO failure (meaning it passed)
    assert evaluator._check_cfr(intent, config) is False


def test_check_cfr_ip_missing(evaluator):
    intent = StructuredIntent(
        original_text="Configure interface with IP 10.1.1.1/24",
        parameters={"ip": "10.1.1.1/24"},
    )
    config = "interface Gig0/1\n description broken"

    # CFR returns True if there IS a failure
    assert evaluator._check_cfr(intent, config) is True


def test_check_cfr_multivendor_partial_missing(evaluator):
    """
    Test CFR with multiple devices where one device's config is missing parameters.
    """
    intent = StructuredIntent(
        original_text="Configure OSPF area 0 between Cisco and Juniper",
        devices=[
            {"name": "R1", "vendor": "cisco"},
            {"name": "J1", "vendor": "juniper"},
        ],
        parameters={"area": "0"},
    )

    # Combined config where Cisco is OK but Juniper is missing area
    config = """
    ! Cisco R1
    router ospf 1
     network 0.0.0.0 255.255.255.255 area 0
    
    # Juniper J1
    set protocols ospf area 1.1.1.1
    """

    # Should flag as failure because '0' is missing from Juniper context
    # This proves the CFR checker is sensitive to missing parameters even in mixed configs.
    assert evaluator._check_cfr(intent, config) is True


def test_evaluation_mode_strict_skips_gns3():
    from unittest.mock import MagicMock
    from run_paper_eval import PaperQualityEvaluator
    from src.schemas.intent import StructuredIntent

    # Mock dependencies
    parser = MagicMock()
    generator = MagicMock()
    validator = MagicMock()
    gns3 = MagicMock()
    hallucination_detector = MagicMock()
    token_counter = MagicMock()

    # Configure mock behavior
    generator.generate.return_value = {
        "Router-A": {
            "config": "interface Gig0/1\nip address 10.1.1.1 255.255.255.0",
            "retrieved_sources": [],
            "valid_source_ids": [],
            "grounding_context": "",
        },
        "_trace": {"master_plan": None},
    }
    # Batfish validator returns FAIL
    validator.validate.return_value = {
        "status": "FAIL",
        "issues": [{"type": "SYNTAX_ERROR", "details": "Syntax error on line 2"}],
    }
    gns3.connected = True

    # Instantiate evaluator in strict mode
    evaluator = PaperQualityEvaluator(
        run_vanilla=False,
        cache_only=False,
        run_gns3=True,
        re_validate=False,
        interactive=False,
        parser=parser,
        generator=generator,
        validator=validator,
        hallucination_detector=hallucination_detector,
        token_counter=token_counter,
        evaluation_mode="strict",
    )
    evaluator.run_gns3 = True
    evaluator.gns3 = gns3

    # Define test intent
    intent = StructuredIntent(
        original_text="Configure interface Gig0/1 with IP 10.1.1.1/24",
        parameters={"ip": "10.1.1.1/24"},
    )

    # Run evaluate_intent
    res = evaluator.evaluate_intent(intent, retrieval_mode="tiered")

    # Assert GNS3 was NOT called (short-circuited)
    gns3.validate.assert_not_called()
    assert res["rag_nettwin"]["functional_status"] == "SKIPPED_FAIL"
    assert (
        "Skipped GNS3 validation due to Batfish failure"
        in res["rag_nettwin"]["functional_errors"][0]
    )


def test_evaluation_mode_observational_runs_gns3():
    from unittest.mock import MagicMock
    from run_paper_eval import PaperQualityEvaluator
    from src.schemas.intent import StructuredIntent

    # Mock dependencies
    parser = MagicMock()
    generator = MagicMock()
    validator = MagicMock()
    gns3 = MagicMock()
    hallucination_detector = MagicMock()
    token_counter = MagicMock()

    # Configure mock behavior
    generator.generate.return_value = {
        "Router-A": {
            "config": "interface Gig0/1\nip address 10.1.1.1 255.255.255.0",
            "retrieved_sources": [],
            "valid_source_ids": [],
            "grounding_context": "",
        },
        "_trace": {"master_plan": None},
    }
    # Batfish validator returns FAIL
    validator.validate.return_value = {
        "status": "FAIL",
        "issues": [{"type": "SYNTAX_ERROR", "details": "Syntax error on line 2"}],
    }
    gns3.connected = True
    gns3.validate.return_value = {
        "status": "FAIL",
        "car": 0.0,
        "is_multi_vendor": False,
        "telnet_logs": {},
        "summary": "GNS3 failed push",
    }

    # Instantiate evaluator in observational mode
    evaluator = PaperQualityEvaluator(
        run_vanilla=False,
        cache_only=False,
        run_gns3=True,
        re_validate=False,
        interactive=False,
        parser=parser,
        generator=generator,
        validator=validator,
        hallucination_detector=hallucination_detector,
        token_counter=token_counter,
        evaluation_mode="observational",
    )
    evaluator.run_gns3 = True
    evaluator.gns3 = gns3

    # Define test intent
    intent = StructuredIntent(
        original_text="Configure interface Gig0/1 with IP 10.1.1.1/24",
        parameters={"ip": "10.1.1.1/24"},
    )

    # Run evaluate_intent
    res = evaluator.evaluate_intent(intent, retrieval_mode="tiered")

    # Assert GNS3 WAS called
    gns3.validate.assert_called_once()
    assert res["rag_nettwin"]["functional_status"] == "FAIL"
    assert res["rag_nettwin"]["car"] == 0.0


def test_groq_key_rotator_rotation():
    import os
    from unittest.mock import patch
    from src.llm.provider import GroqKeyRotator
    from src.config import settings

    # Mock environment variable to load multiple keys and override settings
    with patch.dict(
        os.environ, {"GROQ_API_KEYS": "key1,key2,key3", "GROQ_API_KEY": ""}
    ):
        with patch.object(settings, "groq_api_key", ""):
            rotator = GroqKeyRotator()

            assert rotator.get_keys_count() == 3
            assert rotator.get_current_key() == "key1"

            # First rotation
            assert rotator.rotate_key() is True
            assert rotator.get_current_key() == "key2"

            # Second rotation
            assert rotator.rotate_key() is True
            assert rotator.get_current_key() == "key3"

            # Third rotation wraps around
            assert rotator.rotate_key() is True
            assert rotator.get_current_key() == "key1"


def test_rotating_chat_groq_retries_and_rotates_on_429():
    from unittest.mock import MagicMock, patch
    from src.llm.provider import RotatingChatGroq, GroqKeyRotator
    from langchain_core.messages import HumanMessage

    rotator = GroqKeyRotator()
    rotator._keys = ["key1", "key2"]
    rotator._current_index = 0

    rotating_chat = RotatingChatGroq(
        model_name="kimi-k2-instruct-0905", temperature=0.0, seed=42, rotator=rotator
    )

    # Mock ChatGroq's _generate to fail with 429 on the first key, then succeed
    mock_client1 = MagicMock()
    mock_client1._generate.side_effect = Exception(
        "Rate limit reached. 429 Too Many Requests"
    )

    mock_client2 = MagicMock()
    mock_result = MagicMock()
    mock_client2._generate.return_value = mock_result

    # Side effect function to rebuild clients
    client_mock_map = {"key1": mock_client1, "key2": mock_client2}

    def mock_rebuild():
        current_key = rotating_chat.rotator.get_current_key()
        rotating_chat.client = client_mock_map[current_key]

    with patch.object(rotating_chat, "_rebuild_client", side_effect=mock_rebuild):
        # Force initial mock client
        rotating_chat._rebuild_client()

        # Run invocation
        res = rotating_chat._generate([HumanMessage(content="test")])

        # Assert key rotated to key2 and result returned from client2
        assert rotating_chat.rotator.get_current_key() == "key2"
        assert res == mock_result
        mock_client1._generate.assert_called_once()
        mock_client2._generate.assert_called_once()
