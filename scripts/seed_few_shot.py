import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.rag.vector_store import VectorStore  # noqa: E402
import json


def seed_few_shot():
    store = VectorStore()

    examples = [
        {
            "intent": "Create OSPF area 0 on Router-A for interface Gig0/1.",
            "structured": json.dumps(
                {
                    "protocol": "OSPF",
                    "action": "create",
                    "devices": [
                        {
                            "name": "Router-A",
                            "vendor": "cisco",
                            "os_type": "ios-xe",
                            "os_version": "17.6",
                        }
                    ],
                    "parameters": {"area": "0", "interface": "Gig0/1"},
                    "requirements": [],
                }
            ),
        },
        {
            "intent": "Configure BGP neighbor 10.0.0.2 with remote-as 65001 on Cisco R1.",
            "structured": json.dumps(
                {
                    "protocol": "BGP",
                    "action": "configure",
                    "devices": [
                        {
                            "name": "R1",
                            "vendor": "cisco",
                            "os_type": "ios-xe",
                            "os_version": "17.6",
                        }
                    ],
                    "parameters": {"neighbor_ip": "10.0.0.2", "remote_as": "65001"},
                    "requirements": [],
                }
            ),
        },
        {
            "intent": "Set up a standard ACL 10 to permit traffic from 192.168.1.0/24 on Juniper J1.",
            "structured": json.dumps(
                {
                    "protocol": "ACL",
                    "action": "create",
                    "devices": [
                        {
                            "name": "J1",
                            "vendor": "juniper",
                            "os_type": "junos",
                            "os_version": "21.4",
                        }
                    ],
                    "parameters": {
                        "acl_number": "10",
                        "source_network": "192.168.1.0/24",
                        "action": "permit",
                    },
                    "requirements": [],
                }
            ),
        },
        {
            "intent": "Remove VLAN 100 from all switches.",
            "structured": json.dumps(
                {
                    "protocol": "VLAN",
                    "action": "delete",
                    "devices": [
                        {"name": "Device", "vendor": "cisco", "os_type": "ios-xe"}
                    ],
                    "parameters": {"vlan_id": "100"},
                    "requirements": [],
                }
            ),
        },
        {
            "intent": "Enable interface ge-0/0/0 on Juniper MX240.",
            "structured": json.dumps(
                {
                    "protocol": "Interface",
                    "action": "enable",
                    "devices": [
                        {"name": "MX240", "vendor": "juniper", "os_type": "junos"}
                    ],
                    "parameters": {"interface": "ge-0/0/0"},
                    "requirements": [],
                }
            ),
        },
    ]

    store.add_few_shot_examples(examples)
    print("Few-shot collection seeded successfully.")


if __name__ == "__main__":
    seed_few_shot()
