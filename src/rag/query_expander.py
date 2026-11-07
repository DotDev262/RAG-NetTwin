
import re
from typing import Any

from src.utils import setup_logger

logger = setup_logger("QueryExpander")

# Deterministic domain keyword mappings to expand search recall without LLM token cost
DOMAIN_KEYWORD_MAPPINGS = {
    "ospf": ["router ospf", "network area", "ip ospf hello-interval", "set protocols ospf area"],
    "bgp": ["router bgp", "neighbor remote-as", "address-family ipv4", "set protocols bgp group"],
    "vlan": ["vlan", "switchport access vlan", "switchport mode trunk", "set vlans"],
    "acl": ["ip access-list extended", "permit ip", "deny ip", "set firewall family inet filter"],
    "interface": ["interface GigabitEthernet", "ip address", "no shutdown", "set interfaces unit family inet"],
    "static": ["ip route", "set routing-options static route"],
    "nat": ["ip nat inside source", "ip nat outside", "set security nat"],
}


class QueryExpander:
    """
    Expands a single user intent into multiple semantic search queries
    to improve retrieval recall deterministically without incurring LLM token costs.
    """

    def __init__(self, model_name: str | None = None):
        # Deterministic expansion does not require an LLM instance
        self.model_name = model_name

    def expand(self, query: str) -> list[str]:
        """
        Generates deterministic domain variations of the input query based on
        detected protocol keywords and CLI semantics.
        """
        results = [query]
        q_lower = query.lower()

        # Extract matching domain keywords
        for key, expansions in DOMAIN_KEYWORD_MAPPINGS.items():
            if re.search(rf"\b{re.escape(key)}\b", q_lower):
                for exp in expansions:
                    candidate = f"{query} {exp}"
                    if candidate not in results:
                        results.append(candidate)

        # Cap results to original + 3 expansions
        return results[:4]

