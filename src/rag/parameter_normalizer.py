import abc
import re
import ipaddress
from typing import Dict, Any


class BaseVendorNormalizer(abc.ABC):
    """
    Abstract base class for vendor-specific configuration normalization.
    """

    @abc.abstractmethod
    def normalize_ip_parameters(self, parameters: Dict[str, Any]) -> str:
        """Scan parameters and generate vendor-specific hints."""
        pass

    @abc.abstractmethod
    def post_process_config(self, config: str) -> str:
        """Fix common vendor-specific syntactic errors in the final configuration."""
        pass


class CiscoNormalizer(BaseVendorNormalizer):
    """
    Cisco-specific configuration normalizer.
    """

    def normalize_ip_parameters(self, parameters: Dict[str, Any]) -> str:
        hints = []
        for key, val in parameters.items():
            if not isinstance(val, str):
                continue

            ipv4_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})/(\d+)", val)
            ipv6_match = re.search(r"([0-9a-fA-F:]+)/(\d+)", val)
            match = ipv4_match or ipv6_match

            if match:
                ip_base = match.group(1)
                prefix = match.group(2)

                try:
                    ipaddress.ip_address(ip_base)
                    net = ipaddress.ip_network(f"{ip_base}/{prefix}", strict=False)
                    mask = str(net.netmask)
                    wildcard = str(net.hostmask)

                    if net.version == 6:
                        hints.append(
                            f"For '{key}': Use IPv6 CIDR notation {ip_base}/{prefix} directly, or subnet mask {mask} / wildcard mask {wildcard} if required by the context."
                        )
                    else:
                        hints.append(
                            f"For '{key}': Use IP {ip_base} with wildcard mask {wildcard} (for ACLs/OSPF) or subnet mask {mask} (for interfaces)."
                        )
                except Exception:
                    pass

        if not hints:
            hints.append(
                "Defaults: Use 'Ethernet0/0' for interfaces if none specified."
            )

        return "\n### SYNTACTIC FORMATTING HINTS ###\n" + "\n".join(hints) + "\n"

    def post_process_config(self, config: str) -> str:
        # 0. Strip unwanted deletion 'no' commands at the global level and their nested blocks
        lines = config.splitlines()
        cleaned_lines = []
        skip_indented = False
        deletion_targets = {
            "class-map",
            "policy-map",
            "interface",
            "ip nat",
            "flow",
            "router",
            "access-list",
            "crypto",
            "ip access-list",
        }
        for line in lines:
            stripped = line.strip()
            if skip_indented and (line.startswith(" ") or line.startswith("\t")):
                continue
            else:
                skip_indented = False

            is_deletion = False
            if stripped.lower().startswith("no "):
                cmd_part = stripped[3:].strip().lower()
                if any(cmd_part.startswith(target) for target in deletion_targets):
                    is_deletion = True

            if is_deletion:
                skip_indented = True
                continue

            cleaned_lines.append(line)
        processed = "\n".join(cleaned_lines)

        def replace_cidr(match):
            prefix_cmd = match.group(1)  # e.g., "ip route" or "ipv6 route"
            ip = match.group(2)
            prefix = match.group(3)
            try:
                # Dynamic subnet mask calculation using ipaddress library
                net = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
                if net.version == 6:
                    return f"{prefix_cmd} {ip}/{prefix}"
                else:
                    return f"{prefix_cmd} {ip} {net.netmask}"
            except Exception:
                if ":" in ip:
                    return f"{prefix_cmd} {ip}/{prefix}"
                return f"{prefix_cmd} {ip} 255.255.255.0"

        # 1. Fix 'ip route 10.0.0.0/24 ...' -> 'ip route 10.0.0.0 255.255.255.0 ...'
        # and keep 'ipv6 route 2001:db8::/64 ...' as is
        processed = re.sub(
            r"\b((?:ip|ipv6) route\s+([0-9a-fA-F.:]+))/(\d+)",
            replace_cidr,
            processed,
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
        for short, full in interface_maps.items():
            pattern = rf"\b{short}(\s*\d+(?:/\d+)*)"
            processed = re.sub(pattern, rf"{full}\1", processed, flags=re.IGNORECASE)

        # Convert three-tier interfaces (e.g. Ethernet1/0/24) to two-tier (Ethernet0/0)
        def map_three_tier_interface(match):
            full_name = match.group(1)
            port = int(match.group(4))
            mapped_port = port % 4
            return f"{full_name}0/{mapped_port}"

        processed = re.sub(
            r"\b(Ethernet)(\d+)/(\d+)/(\d+)\b",
            map_three_tier_interface,
            processed,
            flags=re.IGNORECASE,
        )

        # Fix standard ACL syntax: 'access-list <1-99> permit/deny ip ...' -> 'access-list <1-99> permit/deny ...'
        processed = re.sub(
            r"\b(access-list\s+[1-9]\d?\s+(?:permit|deny))\s+ip\b",
            r"\1",
            processed,
            flags=re.IGNORECASE,
        )

        # 3. Clean up QoS 'type qos' and 'type traffic' (NX-OS/XR leakage)
        processed = re.sub(
            r"(class-map|class|policy-map|service-policy)\s+type\s+(traffic|qos)(?:\s+|$)",
            r"\1 ",
            processed,
            flags=re.IGNORECASE,
        )

        # 4. Normalize DSCP values to numeric
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

        # 5. Structural Repair for Cisco QoS
        if "policy-map" in processed and "set dscp" in processed:
            cm_match = re.search(
                r"\bclass-map\s+(?:match-all|match-any|)\s*(\S+)", processed
            )
            acl_match = re.search(
                r"\b(?:ip\s+access-list\s+\S+\s+|access-list\s+)(\d+|\S+)", processed
            )

            if cm_match:
                cm_name = cm_match.group(1)

                lines_cm = processed.splitlines()
                repaired_lines_cm = []
                in_class_map = False
                class_map_has_match = False

                for line in lines_cm:
                    stripped = line.strip()
                    if stripped.startswith("class-map "):
                        in_class_map = True
                        class_map_has_match = False
                    elif in_class_map and (
                        line.startswith(" ") or line.startswith("\t")
                    ):
                        if stripped.startswith("match "):
                            class_map_has_match = True
                    elif in_class_map:
                        if not class_map_has_match:
                            match_val = acl_match.group(1) if acl_match else "101"
                            match_type = (
                                "access-group"
                                if match_val.isdigit()
                                else "access-group name"
                            )
                            repaired_lines_cm.append(f" match {match_type} {match_val}")
                        in_class_map = False

                    repaired_lines_cm.append(line)

                if in_class_map and not class_map_has_match:
                    match_val = acl_match.group(1) if acl_match else "101"
                    match_type = (
                        "access-group" if match_val.isdigit() else "access-group name"
                    )
                    repaired_lines_cm.append(f" match {match_type} {match_val}")

                processed = "\n".join(repaired_lines_cm)

                lines_pm = processed.splitlines()
                repaired_lines_pm = []
                in_policy_map = False
                in_class = False

                for line in lines_pm:
                    stripped = line.strip()
                    if stripped.startswith("policy-map "):
                        in_policy_map = True
                        in_class = False
                    elif in_policy_map:
                        if stripped.startswith("class "):
                            in_class = True
                        elif (
                            stripped.startswith("set ")
                            or stripped.startswith("bandwidth ")
                            or stripped.startswith("priority ")
                            or stripped.startswith("police ")
                            or stripped.startswith("shape ")
                        ) and not in_class:
                            repaired_lines_pm.append(f" class {cm_name}")
                            line = "  " + stripped
                            in_class = True
                        elif not (
                            line.startswith(" ") or line.startswith("\t")
                        ) and not (
                            stripped.startswith("class ")
                            or stripped.startswith("set ")
                            or stripped.startswith("bandwidth ")
                            or stripped.startswith("priority ")
                            or stripped.startswith("police ")
                            or stripped.startswith("shape ")
                        ):
                            in_policy_map = False
                            in_class = False

                    repaired_lines_pm.append(line)
                processed = "\n".join(repaired_lines_pm)

        return processed


class JuniperNormalizer(BaseVendorNormalizer):
    """
    Juniper-specific configuration normalizer.
    """

    def normalize_ip_parameters(self, parameters: Dict[str, Any]) -> str:
        hints = []
        for key, val in parameters.items():
            if not isinstance(val, str):
                continue

            ipv4_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})/(\d+)", val)
            ipv6_match = re.search(r"([0-9a-fA-F:]+)/(\d+)", val)
            match = ipv4_match or ipv6_match

            if match:
                ip_base = match.group(1)
                prefix = match.group(2)
                try:
                    ipaddress.ip_address(ip_base)
                    hints.append(
                        f"For '{key}': Use CIDR notation {ip_base}/{prefix} directly."
                    )
                except Exception:
                    pass

        if not hints:
            hints.append("Defaults: Use 'ge-0/0/0' for interfaces if none specified.")

        return "\n### SYNTACTIC FORMATTING HINTS ###\n" + "\n".join(hints) + "\n"

    def post_process_config(self, config: str) -> str:
        return config


class VyOSNormalizer(BaseVendorNormalizer):
    """
    VyOS-specific configuration normalizer.
    """

    def normalize_ip_parameters(self, parameters: Dict[str, Any]) -> str:
        hints = []
        for key, val in parameters.items():
            if not isinstance(val, str):
                continue

            ipv4_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})/(\d+)", val)
            ipv6_match = re.search(r"([0-9a-fA-F:]+)/(\d+)", val)
            match = ipv4_match or ipv6_match

            if match:
                ip_base = match.group(1)
                prefix = match.group(2)
                try:
                    ipaddress.ip_address(ip_base)
                    hints.append(
                        f"For '{key}': Use CIDR notation {ip_base}/{prefix} directly."
                    )
                except Exception:
                    pass

        if not hints:
            hints.append(
                "Defaults: Use 'eth1' for interfaces if none specified (eth0 reserved for management)."
            )

        return "\n### SYNTACTIC FORMATTING HINTS ###\n" + "\n".join(hints) + "\n"

    def post_process_config(self, config: str) -> str:
        return config


class ParameterNormalizer:
    """
    Utility class to normalize network parameters for specific vendors.
    Specifically handles IP address/mask to Cisco wildcard conversions.
    """

    @staticmethod
    def _get_normalizer(vendor: str) -> BaseVendorNormalizer:
        vendor_clean = (vendor or "cisco").lower().strip()
        if vendor_clean == "juniper":
            return JuniperNormalizer()
        elif vendor_clean == "vyos":
            return VyOSNormalizer()
        else:
            return CiscoNormalizer()

    @staticmethod
    def normalize_ip_parameters(parameters: Dict[str, Any], vendor: str) -> str:
        """
        Scans parameters for IP/CIDR strings and generates vendor-specific hints.
        """
        normalizer = ParameterNormalizer._get_normalizer(vendor)
        return normalizer.normalize_ip_parameters(parameters)

    @staticmethod
    def post_process_config(config: str, vendor: str) -> str:
        """
        Final pass to fix common syntactic errors that Batfish/GNS3 reject.
        Example: Converting CIDR to Mask for Cisco static routes.
        """
        normalizer = ParameterNormalizer._get_normalizer(vendor)
        return normalizer.post_process_config(config)
