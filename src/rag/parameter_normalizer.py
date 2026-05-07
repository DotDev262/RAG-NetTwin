import re
from typing import Dict, Any


class ParameterNormalizer:
    """
    Utility class to normalize network parameters for specific vendors.
    Specifically handles IP address/mask to Cisco wildcard conversions.
    """

    @staticmethod
    def normalize_ip_parameters(parameters: Dict[str, Any], vendor: str) -> str:
        """
        Scans parameters for IP/CIDR strings and generates vendor-specific hints.
        """
        hints = []
        vendor = vendor.lower()

        # CIDR to Mask map
        cidr_to_mask = {
            "0": "0.0.0.0",
            "8": "255.0.0.0",
            "16": "255.255.0.0",
            "24": "255.255.255.0",
            "25": "255.255.255.128",
            "26": "255.255.255.192",
            "27": "255.255.255.224",
            "28": "255.255.255.240",
            "29": "255.255.255.248",
            "30": "255.255.255.252",
            "31": "255.255.255.254",
            "32": "255.255.255.255",
        }

        # CIDR to Wildcard map (Cisco style)
        cidr_to_wildcard = {
            "0": "255.255.255.255",
            "8": "0.255.255.255",
            "16": "0.0.255.255",
            "24": "0.0.0.255",
            "25": "0.0.0.127",
            "26": "0.0.0.63",
            "27": "0.0.0.31",
            "28": "0.0.0.15",
            "29": "0.0.0.7",
            "30": "0.0.0.3",
            "31": "0.0.0.1",
            "32": "0.0.0.0",
        }

        for key, val in parameters.items():
            if not isinstance(val, str):
                continue

            # Check for CIDR notation (e.g., 10.0.0.0/24)
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)/(\d+)", val)
            if match:
                ip_base = match.group(1)
                prefix = match.group(2)

                if vendor == "cisco":
                    mask = cidr_to_mask.get(prefix)
                    wildcard = cidr_to_wildcard.get(prefix)
                    if wildcard:
                        hints.append(
                            f"For '{key}': Use IP {ip_base} with wildcard mask {wildcard} (for ACLs/OSPF) or subnet mask {mask} (for interfaces)."
                        )
                elif vendor == "juniper":
                    hints.append(
                        f"For '{key}': Use CIDR notation {ip_base}/{prefix} directly."
                    )

        if not hints:
            return ""

        return "\n### SYNTACTIC FORMATTING HINTS ###\n" + "\n".join(hints) + "\n"
