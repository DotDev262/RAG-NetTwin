import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock
from parser.intent_parser import StructuredIntent
from run_paper_eval import PaperQualityEvaluator

class MockEvaluator(PaperQualityEvaluator):
    def __init__(self):
        # Skip the heavy initialization
        self.vanilla_llm = None
        self.rag_cache = {}
        self.vanilla_cache = {}

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
    assert "10.1.1.1/24" in tree["interfaces"]["ge-0/0/0"]["unit"]["0"]["family"]["inet"]["address"]
    assert "protocols" in tree
    assert "ospf" in tree["protocols"]

def test_check_cfr_cisco_ast(evaluator):
    # Mock intent
    intent = StructuredIntent(
        original_text="Configure OSPF area 0 on Gig1 with IP 10.1.1.1/24",
        intent_type="routing",
        devices=[{"name": "R1", "vendor": "cisco"}],
        parameters={"ip": "10.1.1.1", "area": "0", "interface": "GigabitEthernet1"}
    )
    
    # Valid config
    config = """
    interface GigabitEthernet1
     ip address 10.1.1.1 255.255.255.0
    router ospf 1
     network 10.1.1.0 0.0.0.255 area 0
    """
    
    # Should NOT fail (return False)
    assert evaluator._check_cfr(intent, config) is False

def test_check_cfr_cisco_ast_missing(evaluator):
    intent = StructuredIntent(
        original_text="Configure OSPF area 0",
        intent_type="routing",
        devices=[{"name": "R1", "vendor": "cisco"}],
        parameters={"area": "99"} # Intent asks for area 99
    )
    
    config = """
    router ospf 1
     network 10.1.1.0 0.0.0.255 area 0
    """
    
    # Should fail (return True) because area 99 is missing
    assert evaluator._check_cfr(intent, config) is True

def test_check_cfr_junos_structured(evaluator):
    intent = StructuredIntent(
        original_text="Set interface ge-0/0/0 IP to 192.168.1.1/24",
        intent_type="interface",
        devices=[{"name": "J1", "vendor": "juniper"}],
        parameters={"ip": "192.168.1.1/24"}
    )
    
    config = "set interfaces ge-0/0/0 unit 0 family inet address 192.168.1.1/24"
    
    # Should NOT fail
    assert evaluator._check_cfr(intent, config) is False

def test_check_cfr_junos_missing(evaluator):
    intent = StructuredIntent(
        original_text="Set AS 65001",
        intent_type="bgp",
        devices=[{"name": "J1", "vendor": "juniper"}],
        parameters={"as": "65001"}
    )
    
    config = "set routing-options autonomous-system 65002"
    
    # Should fail because 65001 is missing
    assert evaluator._check_cfr(intent, config) is True
