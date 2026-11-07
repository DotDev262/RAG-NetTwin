"""
Comprehensive Unit Tests for RAG-NetTwin v2:
1. Module 1: State-Invariant Graph Controller (Synthesis-Time Guardrail)
2. Module 2: Topology-Aware Validation Pipeline (Pre-Emulation Intermediate Tier)
3. Integration with Batfish Static Analysis
"""

import pytest
import networkx as nx
from src.schemas.intent import StructuredIntent, DeviceIntent, ActionType
from src.rag.state_graph_controller import StateInvariantGraphController
from src.validation.topology_validator import TopologyAwareValidator, TopologyErrorType
from src.validation.batfish_validator import BatfishValidator


@pytest.fixture
def sample_ospf_intent():
    return StructuredIntent(
        intent_id="TEST-OSPF-01",
        protocol="OSPF",
        action=ActionType.CONFIGURE,
        devices=[
            DeviceIntent(name="Router-A", vendor="cisco", os_type="ios-xe", os_version="17.6"),
            DeviceIntent(name="Router-B", vendor="cisco", os_type="ios-xe", os_version="17.6"),
        ],
        parameters={
            "area": "0",
            "subnet": "10.10.10.0/30",
            "hello_interval": 5,
            "dead_interval": 20,
            "auth_key": "SECUREKEY123",
        },
        original_text="Configure OSPF Area 0 between Router-A and Router-B on 10.10.10.0/30 with hello 5 and key SECUREKEY123.",
    )


@pytest.fixture
def sample_bgp_intent():
    return StructuredIntent(
        intent_id="TEST-BGP-01",
        protocol="BGP",
        action=ActionType.CONFIGURE,
        devices=[
            DeviceIntent(name="Router-A", vendor="cisco", os_type="ios-xe", os_version="17.6"),
            DeviceIntent(name="Router-B", vendor="juniper", os_type="junos", os_version="21.4"),
        ],
        parameters={
            "local_as": "65001",
            "remote_as": "65002",
            "subnet": "172.16.0.0/30",
        },
        original_text="Establish eBGP between Router-A (AS 65001) and Router-B (AS 65002).",
    )


class TestStateInvariantGraphController:
    """Tests for Module 1: StateInvariantGraphController."""

    def test_build_topology_from_intent(self, sample_ospf_intent):
        controller = StateInvariantGraphController()
        g = controller.build_topology_from_intent(sample_ospf_intent)

        assert isinstance(g, nx.Graph)
        assert "Router-A" in g.nodes
        assert "Router-B" in g.nodes
        assert g.has_edge("Router-A", "Router-B")

        edge_data = g.get_edge_data("Router-A", "Router-B")
        assert edge_data["subnet"] == "10.10.10.0/30"
        assert edge_data["ospf_area"] == "0"
        assert edge_data["auth_key"] == "SECUREKEY123"

    def test_extract_state_invariants(self, sample_ospf_intent):
        controller = StateInvariantGraphController()
        invariants = controller.extract_state_invariants(sample_ospf_intent)

        inv_types = [inv.invariant_type for inv in invariants]
        assert "SHARED_LINK_SUBNET" in inv_types
        assert "OSPF_AREA_ID" in inv_types
        assert "OSPF_AUTH_KEY" in inv_types
        assert "OSPF_TIMERS" in inv_types

    def test_build_constraint_injection_prompt(self, sample_ospf_intent):
        controller = StateInvariantGraphController()
        prompt = controller.build_constraint_injection_prompt(sample_ospf_intent)

        assert "STATE-INVARIANT GRAPH CONTROLLER: MANDATORY INVARIANTS" in prompt
        assert "OSPF_AREA_ID" in prompt
        assert "10.10.10.0/30" in prompt
        assert "SECUREKEY123" in prompt

    def test_intercept_conflict_detection(self, sample_ospf_intent):
        controller = StateInvariantGraphController()

        # Simulate conflicting configurations between adjacent nodes
        configs = {
            "Router-A": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.1 255.255.255.252\n"
                " ip ospf 1 area 0\n"
                " ip ospf hello-interval 5\n"
            ),
            "Router-B": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.2 255.255.255.252\n"
                " ip ospf 1 area 1\n"  # Area mismatch!
                " ip ospf hello-interval 10\n"  # Timer mismatch!
            ),
        }

        result = controller.intercept_and_validate(sample_ospf_intent, configs)
        assert result.has_conflicts is True
        error_types = [c["type"] for c in result.conflicts]
        assert "OSPF_AREA_MISMATCH" in error_types
        assert "OSPF_HELLO_MISMATCH" in error_types
        assert result.remediation_prompt is not None
        assert "STATE-INVARIANT GRAPH CONTROLLER INTERCEPTION" in result.remediation_prompt

    def test_intercept_no_conflicts(self, sample_ospf_intent):
        controller = StateInvariantGraphController()

        # Consistent configs
        configs = {
            "Router-A": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.1 255.255.255.252\n"
                " ip ospf 1 area 0\n"
                " ip ospf hello-interval 5\n"
            ),
            "Router-B": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.2 255.255.255.252\n"
                " ip ospf 1 area 0\n"
                " ip ospf hello-interval 5\n"
            ),
        }

        result = controller.intercept_and_validate(sample_ospf_intent, configs)
        assert result.has_conflicts is False
        assert len(result.conflicts) == 0


class TestTopologyAwareValidator:
    """Tests for Module 2: TopologyAwareValidator (Tier 1.5)."""

    def test_ospf_area_and_timer_mismatch(self, sample_ospf_intent):
        validator = TopologyAwareValidator()
        configs = {
            "Router-A": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.1 255.255.255.252\n"
                " ip ospf 1 area 0\n"
                " ip ospf hello-interval 5\n"
            ),
            "Router-B": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.2 255.255.255.252\n"
                " ip ospf 1 area 51\n"  # Mismatch
                " ip ospf hello-interval 15\n"  # Mismatch
            ),
        }

        report = validator.validate(configs, sample_ospf_intent)
        assert report["status"] == "FAIL"
        err_types = [i["error_type"] for i in report["issues"]]
        assert TopologyErrorType.OSPF_AREA_MISMATCH in err_types
        assert TopologyErrorType.OSPF_TIMER_MISMATCH in err_types

    def test_mtu_mismatch(self, sample_ospf_intent):
        validator = TopologyAwareValidator()
        configs = {
            "Router-A": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.1 255.255.255.252\n"
                " mtu 1500\n"
                " ip ospf 1 area 0\n"
            ),
            "Router-B": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.2 255.255.255.252\n"
                " mtu 9000\n"  # Jumbo frame mismatch!
                " ip ospf 1 area 0\n"
            ),
        }

        report = validator.validate(configs, sample_ospf_intent)
        assert report["status"] == "FAIL"
        err_types = [i["error_type"] for i in report["issues"]]
        assert TopologyErrorType.OSPF_MTU_MISMATCH in err_types

    def test_bgp_session_parameters(self, sample_bgp_intent):
        validator = TopologyAwareValidator()
        configs = {
            "Router-A": (
                "router bgp 65001\n"
                " neighbor 172.16.0.2 remote-as 65002\n"
                " neighbor 172.16.0.2 password secret1\n"
            ),
            "Router-B": (
                "set protocols bgp local-as 65002\n"
                "set protocols bgp neighbor 172.16.0.1 remote-as 99999\n"  # Misconfigured ASN
                "set protocols bgp neighbor 172.16.0.1 password wrongkey\n"  # Mismatched password
            ),
        }

        report = validator.validate(configs, sample_bgp_intent)
        assert report["status"] == "FAIL"
        err_types = [i["error_type"] for i in report["issues"]]
        assert TopologyErrorType.BGP_REMOTE_AS_MISMATCH in err_types
        assert TopologyErrorType.BGP_AUTH_MISMATCH in err_types

    def test_acl_directional_logic(self):
        validator = TopologyAwareValidator()
        ingress_intent = StructuredIntent(
            intent_id="ACL-IN-01",
            protocol="ACL",
            action=ActionType.CONFIGURE,
            devices=[DeviceIntent(name="Router-A", vendor="cisco")],
            parameters={"direction": "in"},
            original_text="Block incoming SSH ingress traffic on GigabitEthernet0/1",
        )

        # Inverted configuration: applied 'out' instead of 'in'
        wrong_dir_config = {
            "Router-A": (
                "ip access-list extended BLOCK_SSH\n"
                " deny tcp any any eq 22\n"
                " permit ip any any\n"
                "interface GigabitEthernet0/1\n"
                " ip access-group BLOCK_SSH out\n"  # Error! Direction should be 'in'
            )
        }

        report = validator.validate(wrong_dir_config, ingress_intent)
        assert report["status"] == "FAIL"
        err_types = [i["error_type"] for i in report["issues"]]
        assert TopologyErrorType.ACL_DIRECTION_ERROR in err_types

    def test_batfish_and_topology_validator_pipeline(self, sample_ospf_intent):
        """Validates tier ordering: Batfish Tier 1 passes syntax, then Topology-Aware validates semantics."""
        batfish = BatfishValidator()
        topo_val = TopologyAwareValidator()

        # Syntactically valid config that has semantic Area mismatch
        configs = {
            "Router-A": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.1 255.255.255.252\n"
                " ip ospf 1 area 0\n"
            ),
            "Router-B": (
                "interface GigabitEthernet0/1\n"
                " ip address 10.10.10.2 255.255.255.252\n"
                " ip ospf 1 area 100\n"
            ),
        }

        # Batfish Tier 1 Static Analysis check
        if batfish.session is not None:
            bf_result = batfish.validate(configs, sample_ospf_intent)
            assert bf_result["status"] in ["PASS", "WARNING"]

        # Tier 1.5 Topology-Aware Semantic Validator catches the cross-device invariant failure
        topo_result = topo_val.validate(configs, sample_ospf_intent)
        assert topo_result["status"] == "FAIL"
        assert TopologyErrorType.OSPF_AREA_MISMATCH in [i["error_type"] for i in topo_result["issues"]]
