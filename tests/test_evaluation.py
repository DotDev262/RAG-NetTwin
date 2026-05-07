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
