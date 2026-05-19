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
                elif vendor in ["juniper", "vyos"]:
                    hints.append(
                        f"For '{key}': Use CIDR notation {ip_base}/{prefix} directly."
                    )

        if not hints:
            # Fallback to generic defaults if no specific hints (Fix F17: Generic Defaults)
            if vendor == "cisco":
                hints.append(
                    "Defaults: Use 'Ethernet0/0' for interfaces if none specified."
                )
            elif vendor == "vyos":
                hints.append(
                    "Defaults: Use 'eth1' for interfaces if none specified (eth0 reserved for management)."
                )
            elif vendor == "juniper":
                hints.append(
                    "Defaults: Use 'ge-0/0/0' for interfaces if none specified."
                )

        return "\n### SYNTACTIC FORMATTING HINTS ###\n" + "\n".join(hints) + "\n"

    @staticmethod
    def post_process_config(config: str, vendor: str) -> str:
        """
        Final pass to fix common syntactic errors that Batfish/GNS3 reject.
        Example: Converting CIDR to Mask for Cisco static routes.
        """
        vendor = (vendor or "cisco").lower()
        if vendor != "cisco":
            return config

        cidr_to_mask = {
            "0": "0.0.0.0",
            "8": "255.0.0.0",
            "16": "255.255.0.0",
            "24": "255.255.255.0",
            "28": "255.255.255.240",
            "30": "255.255.255.252",
            "32": "255.255.255.255",
        }

        def replace_cidr(match):
            ip = match.group(1)
            prefix = match.group(2)
            mask = cidr_to_mask.get(
                prefix, "255.255.255.0"
            )  # Default to /24 if unknown
            return f"{ip} {mask}"

        # 1. Fix 'ip route 10.0.0.0/24 ...' -> 'ip route 10.0.0.0 255.255.255.0 ...'
        processed = re.sub(
            r"(ip route \d+\.\d+\.\d+\.\d+)/(\d+)",
            replace_cidr,
            config,
            flags=re.IGNORECASE,
        )

        # 2. Fix interface abbreviations and map to IOU-compatible names (EthernetX/Y)
        interface_maps = {
            r"GigabitEthernet": r"Ethernet",
            r"Gig": r"Ethernet",
            r"Gi": r"Ethernet",
            r"TenGigabitEthernet": r"Ethernet",
            r"Ten": r"Ethernet",
            r"Te": r"Ethernet",
            r"FastEthernet": r"Ethernet",
            r"Fa": r"Ethernet",
        }
        # Use a more careful replacement that preserves the slot/port numbers
        for short, full in interface_maps.items():
            # Match boundary, then short name, then OPTIONAL space, then digits/slashes
            pattern = rf"\b{short}(\s*\d+(?:/\d+)*)"
            processed = re.sub(pattern, rf"{full}\1", processed, flags=re.IGNORECASE)

        # 3. Clean up QoS 'type qos' and 'type traffic' (NX-OS/XR leakage)
        # Handles: 'class-map type traffic' -> 'class-map', 'no policy-map type qos' -> 'no policy-map'
        # Improved regex to handle optional space at end of line and 'class' keyword
        processed = re.sub(
            r"(class-map|class|policy-map|service-policy)\s+type\s+(traffic|qos)(?:\s+|$)",
            r"\1 ",
            processed,
            flags=re.IGNORECASE,
        )

        # 4. Normalize DSCP values to numeric (Batfish is picky)
        dscp_map = {
            "cs6": "48",
            "ef": "46",
            "cs7": "56",
            "af11": "10",
            "af21": "18",
            "af31": "26",
            "af41": "34",
        }
        for name, num in dscp_map.items():
            processed = re.sub(
                rf"\bset dscp {name}\b",
                f"set dscp {num}",
                processed,
                flags=re.IGNORECASE,
            )

        # 5. Structural Repair for Cisco QoS (fixes flat LLM output)
        if "policy-map" in processed and "set dscp" in processed:
            # Detect first defined class-map and access-list
            cm_match = re.search(
                r"class-map\s+(?:match-all|match-any|)\s*(\S+)", processed
            )
            acl_match = re.search(
                r"(?:ip\s+access-list\s+\S+\s+|access-list\s+)(\d+|\S+)", processed
            )

            if cm_match:
                cm_name = cm_match.group(1)
                # Repair class-map if it's missing a 'match' line
                if (
                    cm_name in processed
                    and "match" not in processed.split(cm_name)[1].split("\n")[1]
                ):
                    match_val = acl_match.group(1) if acl_match else "101"
                    match_type = (
                        "access-group" if match_val.isdigit() else "access-group name"
                    )
                    processed = re.sub(
                        rf"(class-map\s+\S+\s+{cm_name})",
                        rf"\1\n match {match_type} {match_val}",
                        processed,
                    )

                # Repair policy-map if 'set dscp' is flat (not inside a class block)
                if "class" not in processed.split("policy-map")[1].split("set dscp")[0]:
                    processed = re.sub(
                        r"(policy-map\s+\S+)\n(\s*set dscp\s+\d+)",
                        rf"\1\n class {cm_name}\n  \2",
                        processed,
                    )

        return processed
