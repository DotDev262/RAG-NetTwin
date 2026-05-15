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
        {
            "intent": "Align OSPF hello-interval to 5 seconds on Cisco",
            "vendor": "cisco",
            "config": "interface GigabitEthernet0/1\n ip ospf hello-interval 5",
        },
        # JUNIPER EXAMPLES
        {
            "intent": "Enable OSPF area 0 on interface ge-0/0/0.0",
            "vendor": "juniper",
            "config": "set protocols ospf area 0.0.0.0 interface ge-0/0/0.0",
        },
        {
            "intent": "Set OSPF hello-interval to 5 on Juniper",
            "vendor": "juniper",
            "config": "set protocols ospf area 0 interface ge-0/0/0.0 hello-interval 5",
        },
        {
            "intent": "Configure OSPF area 0 between Cisco (Gig0/1) and Juniper (ge-0/0/0.0)",
            "vendor": "cisco",
            "config": "interface GigabitEthernet0/1\n ip address 10.1.1.1 255.255.255.252\n ip ospf 1 area 0\nrouter ospf 1\n network 10.1.1.0 0.0.0.3 area 0",
        },
        {
            "intent": "Configure OSPF area 0 between Cisco (Gig0/1) and Juniper (ge-0/0/0.0)",
            "vendor": "juniper",
            "config": "set interfaces ge-0/0/0 unit 0 family inet address 10.1.1.2/30\nset protocols ospf area 0.0.0.0 interface ge-0/0/0.0",
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
        {
            "intent": "Configure a NAT overload (PAT) for subnet 192.168.10.0/24 on interface Gig0/1",
            "vendor": "cisco",
            "config": "access-list 100 permit 192.168.10.0 0.0.0.255\nip nat inside source list 100 interface GigabitEthernet0/1 overload\ninterface GigabitEthernet0/1\n ip nat outside\ninterface GigabitEthernet0/2\n ip nat inside",
        },
    ]

    store.add_gold_configs(gold_examples)
    print("Gold standard configs seeded successfully.")


if __name__ == "__main__":
    seed_gold_configs()
