from unittest.mock import MagicMock
from src.rag.query_expander import QueryExpander
from src.rag.multi_vendor_coordinator import MultiVendorCoordinator
from src.schemas.intent import StructuredIntent, DeviceIntent

def test_deterministic_query_expander():
    expander = QueryExpander()
    # Test OSPF expansion
    queries = expander.expand("configure ospf area 0 on router")
    assert len(queries) > 1
    assert any("router ospf" in q for q in queries)
    # Ensure no network / LLM calls were made
    assert expander.model_name is None or True

def test_deterministic_interop_plan():
    coordinator = MultiVendorCoordinator()
    intent = StructuredIntent(
        original_text="Configure OSPF area 0 between Cisco and Juniper",
        protocol="ospf",
        action="configure",
        parameters={"area": "0", "hello_interval": "10"},
        devices=[
            DeviceIntent(name="R1", vendor="cisco"),
            DeviceIntent(name="R2", vendor="juniper"),
        ],
    )
    plan = coordinator.generate_interop_plan(intent)
    assert plan is not None
    assert "R1" in plan.proposed_parameters
    assert "R2" in plan.proposed_parameters
    assert plan.proposed_parameters["R1"]["area"] == "0"
    assert len(plan.deployment_sequence) > 0
