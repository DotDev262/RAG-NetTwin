import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.vector_store import VectorStore  # noqa: E402


def seed_gold_configs():
    store = VectorStore()

    # Gold standard Intent->Config pairs
    gold_examples = [
        # CISCO EXAMPLES
        {
            "intent": "Configure OSPF area 0 on interface GigabitEthernet0/1 with network 10.0.0.0/24",
            "vendor": "cisco",
            "config": "router ospf 1\n network 10.0.0.0 0.0.0.255 area 0\ninterface GigabitEthernet0/1\n ip ospf 1 area 0",
        },
        {
            "intent": "Set up BGP AS 65001 and peer with 10.1.1.1 remote-as 65002",
            "vendor": "cisco",
            "config": "router bgp 65001\n neighbor 10.1.1.1 remote-as 65002\n address-family ipv4\n  neighbor 10.1.1.1 activate",
        },
        {
            "intent": "Create a VLAN 100 named SALES",
            "vendor": "cisco",
            "config": "vlan 100\n name SALES",
        },
        # JUNIPER EXAMPLES
        {
            "intent": "Enable OSPF area 0 on interface ge-0/0/0.0",
            "vendor": "juniper",
            "config": "set protocols ospf area 0.0.0.0 interface ge-0/0/0.0",
        },
        {
            "intent": "Configure BGP peer 10.1.1.2 with autonomous-system 65001 and remote-as 65002",
            "vendor": "juniper",
            "config": "set routing-options autonomous-system 65001\nset protocols bgp group EXTERNAL peer-as 65002\nset protocols bgp group EXTERNAL neighbor 10.1.1.2",
        },
        {
            "intent": "Create VLAN 200 named GUESTS",
            "vendor": "juniper",
            "config": "set vlans GUESTS vlan-id 200",
        },
    ]

    store.add_gold_configs(gold_examples)
    print("Gold standard configs seeded successfully.")


if __name__ == "__main__":
    seed_gold_configs()
