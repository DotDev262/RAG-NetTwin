import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.hallucination_detector import HallucinationDetector

# --- BASE TEST DATA ---
BASE_DOCS = [
    "router ospf",
    "router ospf 100",
    "network area",
    "network 10.0.0.0 0.0.0.255 area 0",
    "interface GigabitEthernet",
    "description Uplink",
    "set protocols bgp",
    "set protocols bgp group EXTERNAL type external"
]

# --- INDUSTRY COMPLEX DOCS (SAD scenarios) ---
INDUSTRY_DOCS = [
    # Layer 2/3 Switching
    "vlan",
    "vlan 100",
    "switchport mode trunk",
    "switchport trunk allowed vlan",
    "spanning-tree mode rapid-pvst",
    "spanning-tree portfast default",
    
    # BGP configurations
    "neighbor 192.168.1.1 remote-as 65001",
    "neighbor 192.168.1.1 activate",
    "neighbor 192.168.1.1 route-map LAN in",
    "address-family ipv4",
    "address-family vpnv4",
    
    # Route maps and prefix lists
    "ip prefix-list PL_SEVEN seq 10 permit 10.0.0.0/8",
    "route-map RM_PERMIT permit 10",
    "route-map RM_DENY deny 20",
    "match ip address prefix-list",
    "set local-preference",
    
    # QoS configurations  
    "class-map",
    "policy-map",
    "service-policy output",
    "bandwidth percent",
    "priority percent",
    
    # HA/Redundancy
    "standby version 2",
    "standby 1 ip 10.1.1.254",
    "standby 1 priority 110",
    
    # Tunnel/VPN
    "interface Tunnel0",
    "ip nhrp network-id",
    "ip nhrp map",
    "tunnel mode gre multipoint",
    
    # Juniper hierarchies
    "set protocols bgp group IBGP type internal",
    "set protocols bgp group IBGP neighbor 10.0.0.1",
    "set routing-options router-id 10.0.0.1",
    "set protocols ospf area 0.0.0.0 interface lo0.0",
]

TEST_CASES = [
    # === ORIGINAL BASIC TESTS ===
    {
        "name": "Fully Grounded Cisco",
        "config": "router ospf 100\n network 10.0.0.0 0.0.0.255 area 0",
        "intent": "Enable OSPF 100 area 0",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Intent-Grounded Parameter (Hostname)",
        "config": "hostname CORE-SWITCH-01",
        "intent": "Set hostname to CORE-SWITCH-01",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Common Boilerplate (Enable/Config)",
        "config": "enable\nconfigure terminal\ninterface Gig0/1",
        "intent": "Go to interface Gig0/1",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Actual Hallucination (Fake Command)",
        "config": "router hyper-ospf 500\n feature-enable high-speed",
        "intent": "Enable OSPF",
        "expected": True,
        "docs": BASE_DOCS
    },
    {
        "name": "Valid Citation ID",
        "config": "router ospf 100",
        "citations": ["doc_001"],
        "valid_ids": ["doc_001", "doc_002"],
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Citations with 'ID:' Prefix (LLM quirk)",
        "config": "router ospf 100",
        "citations": ["ID: doc_001"],
        "valid_ids": ["doc_001"],
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Complex Interface ID (Grounded by Intent)",
        "config": "interface TenGigabitEthernet1/0/24.100",
        "intent": "Configure subinterface TenGigabitEthernet1/0/24.100",
        "expected": False,
        "docs": BASE_DOCS
    },
    
    # === INDUSTRY COMPLEX PATH TESTS ===
    {
        "name": "Industry: BGP Route-Map Grounded",
        "config": "router bgp 65000\n neighbor 192.168.1.1 remote-as 65001\n neighbor 192.168.1.1 route-map LAN in",
        "intent": "Configure BGP peer with route-map",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Industry: Prefix-List Grounded",
        "config": "ip prefix-list PL_SEVEN seq 10 permit 10.0.0.0/8",
        "intent": "Create prefix list for 10.0.0.0/8",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Industry: VLAN Config Grounded",
        "config": "vlan 100\n name ENGINEERING",
        "intent": "Create VLAN 100 for engineering",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Industry: Spanning-Tree Grounded",
        "config": "spanning-tree mode rapid-pvst",
        "intent": "Enable rapid-pvst spanning tree",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Industry: HSRP Grounded",
        "config": "standby version 2\n standby 1 ip 10.1.1.254\n standby 1 priority 110",
        "intent": "Configure HSRP with priority 110",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Industry: Tunnel Config Grounded",
        "config": "interface Tunnel0\n ip nhrp network-id 1\n tunnel mode gre multipoint",
        "intent": "Create GRE tunnel",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    
    # === INDUSTRY SAD HALLUCINATION TESTS ===
    {
        "name": "SAD: BGP Fake Protocol",
        "config": "router cisco-bgp 65001",
        "intent": "Configure BGP",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "SAD: VLAN Fake Mode",
        "config": "switchport mode hyper-virtual",
        "intent": "Configure switchport",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "SAD: QoS Fake Algorithm",
        "config": "priority custom-queue 1",
        "intent": "Configure QoS priority queue",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "SAD: Fake HA Protocol",
        "config": "standby super-redundant mode",
        "intent": "Configure HA",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "SAD: Tunnel Fake Mode",
        "config": "tunnel mode quantum-encrypt",
        "intent": "Configure encrypted tunnel",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    
    # === MULTI-VENDOR SAD TESTS ===
    {
        "name": "Juniper: BGP Group Grounded",
        "config": "set protocols bgp group IBGP type internal",
        "intent": "Configure Juniper IBGP group",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Juniper: OSPF Area Grounded",
        "config": "set protocols ospf area 0.0.0.0 interface lo0.0",
        "intent": "Configure OSPF on loopback",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Juniper: Router-ID Grounded",
        "config": "set routing-options router-id 10.0.0.1",
        "intent": "Set router-id to 10.0.0.1",
        "expected": False,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Juniper: Fake Hierarchy",
        "config": "set protocols zebra-group internal type internal",
        "intent": "Configure routing protocol",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    
    # === EDGE CASES ===
    {
        "name": "Edge: Multiple Hallucinations",
        "config": "router fake-protocol-xyz\n mode hyper-enable",
        "intent": "Configure routing",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Edge: Mixed Valid-Fake",
        "config": "router ospf 100\n router hyper-ospf 200",
        "intent": "Configure OSPF and another protocol",
        "expected": True,
        "docs": INDUSTRY_DOCS
    },
    {
        "name": "Edge: Citation Without Config",
        "config": "router ospf 100",
        "citations": ["invalid_ref"],
        "valid_ids": ["doc_001"],
        "expected": True,
        "docs": BASE_DOCS
    },
    
    # === NEW ADVANCED TESTS ===
    {
        "name": "Advanced: IPv6 Grounded",
        "config": "ipv6 route 2001:db8::/32 GigabitEthernet1",
        "intent": "Add IPv6 route",
        "expected": False,
        "docs": ["ipv6 route prefix interface", "ipv6 unicast-routing"]
    },
    {
        "name": "Advanced: Case Insensitivity",
        "config": "ROUTER OSPF 100\n NETWORK 10.0.0.0 0.0.0.255 AREA 0",
        "intent": "Enable OSPF",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Advanced: Mixed Citations (Valid+Invalid)",
        "config": "router ospf 100",
        "citations": ["doc_001", "malformed_999"],
        "valid_ids": ["doc_001", "doc_002"],
        "expected": True,
        "docs": BASE_DOCS
    },
    {
        "name": "Advanced: Long Description (False Positive Check)",
        "config": "interface Gig0/1\n description This is a very long description with multiple words that are not in docs",
        "intent": "Set description on Gig0/1",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Advanced: Nested Juniper Hierarchy",
        "config": "set security zones security-zone TRUST interfaces ge-0/0/0.0",
        "intent": "Add interface to trust zone",
        "expected": False,
        "docs": ["set security zones security-zone"]
    },
    {
        "name": "Advanced: IPv6 Fake Protocol",
        "config": "ipv6 router hyper-rip",
        "intent": "Configure IPv6 RIP",
        "expected": True,
        "docs": ["ipv6 router rip", "ipv6 router ospf"]
    },
    {
        "name": "Advanced: Empty Config",
        "config": "",
        "intent": "Do nothing",
        "expected": False,
        "docs": BASE_DOCS
    },
    {
        "name": "Advanced: Comment Only",
        "config": "! This is just a comment\n# Another comment",
        "intent": "Add comments",
        "expected": False,
        "docs": BASE_DOCS
    },
]

@pytest.fixture
def detector():
    return HallucinationDetector()

@pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: c["name"])
def test_hallucination_detector(detector, case):
    docs = case.get("docs", BASE_DOCS)
    report = detector.detect(
        config=case["config"],
        citations=case.get("citations", []),
        valid_source_ids=case.get("valid_ids", []),
        retrieved_texts=docs,
        intent_context=case.get("intent", "")
    )
    
    assert report.is_hallucinated == case["expected"], f"Failed: {case['name']} - Reason: {report.reason}"
