import re
import json
from typing import Dict, Any
from ciscoconfparse import CiscoConfParse  # type: ignore
from src.utils import setup_logger

logger = setup_logger("CFRChecker")


class CFRChecker:
    """
    Configuration Faithfulness Recognition (CFR) Check:
    Detects if critical intent parameters are missing in generated configs.
    """

    def check(self, intent, config: str) -> bool:
        if not intent.parameters or not config:
            return False

        config_clean = config.strip()
        if not config_clean:
            return False

        is_juniper = (
            any(
                config_clean.startswith(prefix)
                for prefix in [
                    "set ",
                    "firewall",
                    "protocols ",
                    "interfaces ",
                    "routing-options",
                ]
            )
            or "set " in config_clean[:1000]
        )

        parse = None
        if not is_juniper:
            try:
                parse = CiscoConfParse(config.splitlines(), syntax="ios")
            except Exception as e:
                logger.warning(
                    f"CiscoConfParse failed to initialize: {e}. Falling back to regex."
                )

        for key, val in intent.parameters.items():
            key_lower = key.lower()
            # Use word boundaries to avoid 'description' matching 'ip'
            is_critical = any(
                re.search(rf"\b{re.escape(k)}\b", key_lower)
                for k in [
                    "ip",
                    "address",
                    "mask",
                    "netmask",
                    "neighbor",
                    "as",
                    "area",
                    "vlan",
                    "remote",
                    "port",
                    "gateway",
                    "subnet",
                ]
            )
            # Special case for 'vlan' which often appears in keys like 'vlan_list'
            if not is_critical and "vlan" in key_lower:
                is_critical = True

            if not is_critical:
                continue

            if isinstance(val, list):
                vals = val
            elif isinstance(val, str) and val.startswith("[") and val.endswith("]"):
                try:
                    # Fix Python-isms in LLM output
                    json_val = (
                        val.replace("True", "true")
                        .replace("False", "false")
                        .replace("None", "null")
                    )
                    vals = json.loads(json_val)
                    if not isinstance(vals, list):
                        vals = [val]
                except Exception:
                    vals = [val]
            else:
                vals = [val]

            for v in vals:
                val_str = str(v).strip()

                if parse and not is_juniper:
                    found = False
                    if "." in val_str and self._is_ip_like(val_str):
                        if parse.find_objects(re.escape(val_str)):
                            found = True
                    elif "vlan" in key_lower:
                        if parse.find_objects(
                            f"^vlan {re.escape(val_str)}$"
                        ) or parse.find_objects(f"vlan {re.escape(val_str)}"):
                            found = True
                    elif any(k in key_lower for k in ["as", "area", "neighbor"]):
                        if parse.find_objects(re.escape(val_str)):
                            found = True
                    if found:
                        continue

                if is_juniper:
                    junos_tree = self._junos_config_to_dict(config)
                    if self._check_junos_parameter(junos_tree, key_lower, val_str):
                        continue
                    if "." in val_str and self._is_ip_like(val_str):
                        if self._config_contains_ip(config, val_str):
                            continue
                    return True

                if "/" in val_str and val_str.split("/")[0].replace(".", "").isdigit():
                    if not self._config_contains_ip(config, val_str):
                        return True
                elif any(c.isdigit() for c in val_str) and "." not in val_str:
                    if not self._config_contains_value(config, key, val_str):
                        return True
                elif "." in val_str and self._is_ip_like(val_str):
                    if not self._config_contains_ip(config, val_str):
                        return True
                else:
                    if not re.search(
                        rf"\b{re.escape(val_str.lower())}\b", config.lower()
                    ):
                        return True
        return False

    def _is_ip_like(self, val: str) -> bool:
        parts = val.replace("/", " ").split()
        if parts:
            first_part = parts[0]
            return all(part.isdigit() for part in first_part.split("."))
        return False

    def _config_contains_ip(self, config: str, ip_with_prefix: str) -> bool:
        if "/" in ip_with_prefix:
            parts = ip_with_prefix.split("/")
            ip_base = parts[0]
            intent_prefix = parts[1]
        else:
            ip_base = ip_with_prefix
            intent_prefix = None

        ip_pattern = r"\d+\.\d+\.\d+\.\d+"
        config_ips = re.findall(ip_pattern, config)
        if ip_base not in config_ips:
            return False
        if not intent_prefix:
            return True

        prefix_to_mask = {
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
        prefix_to_wildcard = {
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

        intent_mask = prefix_to_mask.get(intent_prefix)
        intent_wildcard = prefix_to_wildcard.get(intent_prefix)
        perfect_match = False
        is_acl_context = "access-list" in config.lower() or "acl" in config.lower()

        for line in config.split("\n"):
            if ip_base not in line:
                continue
            cidr_match = re.search(rf"{re.escape(ip_base)}/(\d+)", line)
            if cidr_match:
                if cidr_match.group(1) == intent_prefix:
                    perfect_match = True
                    break
                continue
            if intent_mask and intent_mask in line:
                perfect_match = True
                break
            if intent_wildcard and intent_wildcard in line:
                perfect_match = True
                break
            if is_acl_context:
                wildcard_match = re.search(
                    r"(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", line
                )
                if wildcard_match:
                    potential_wildcard = wildcard_match.group(2)
                    if intent_wildcard and potential_wildcard == intent_wildcard:
                        perfect_match = True
                        break
            has_mask = any(m in line for m in prefix_to_mask.values())
            has_wildcard = any(w in line for w in prefix_to_wildcard.values())
            has_cidr = "/2" in line or "/1" in line
            if not (has_mask or has_cidr or has_wildcard):
                perfect_match = True
        return perfect_match

    def _config_contains_value(self, config: str, param_key: str, value: str) -> bool:
        keyword_patterns = {
            "vlan": r"vlan\s+",
            "area": r"area\s+",
            "as": r"(?:remote-as|autonomous-system|as)\s+",
            "neighbor": r"neighbor\s+",
            "remote": r"remote-as\s+",
            "port": r"(?:eq|port)\s+",
            "mtu": r"mtu\s+",
            "priority": r"priority\s+",
            "cost": r"cost\s+",
            "bandwidth": r"bandwidth\s+",
            "hello": r"hello-interval\s+",
        }
        key_lower = param_key.lower()
        for kw, pattern in keyword_patterns.items():
            if kw in key_lower:
                # Allow comma or space as delimiter after the value, and allow other chars after keyword (for lists)
                combined_pattern = f"{pattern}(?:[^\\n]*?){re.escape(value)}(?:\\s|,|$)"
                return bool(re.search(combined_pattern, config, re.IGNORECASE))
        standalone_pattern = f"(?<![\\w/]){re.escape(value)}(?![\\w/])"
        return bool(re.search(standalone_pattern, config))

    def _junos_config_to_dict(self, config: str) -> Dict[str, Any]:
        tree: Dict[str, Any] = {}
        for line in config.splitlines():
            line = line.strip()
            if not line or not line.startswith("set "):
                continue
            parts = line[4:].split()
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
        return tree

    def _check_junos_parameter(self, tree: Dict, key: str, value: str) -> bool:
        key_aliases = {
            "vlan": ["vlan-id", "vlan"],
            "area": ["area", "area-id"],
            "as": ["autonomous-system", "as-number", "routing-options"],
            "mtu": ["mtu"],
            "cost": ["metric", "cost"],
            "priority": ["priority"],
        }
        target_keys = [key.lower()]
        for k, aliases in key_aliases.items():
            if k in key.lower():
                target_keys.extend(aliases)

        def normalize_junos_val(v):
            v = str(v).lower()
            return "0" if v == "0.0.0.0" else v

        v_norm = normalize_junos_val(value)

        def find_in_context(t, v, in_context=False):
            for k in t:
                k_str = str(k).lower()
                is_target = any(tk == k_str for tk in target_keys)
                level_context = in_context or is_target
                if v == normalize_junos_val(k) and level_context:
                    return True
                if isinstance(t[k], dict):
                    if find_in_context(t[k], v, level_context):
                        return True
                elif v == normalize_junos_val(t[k]) and level_context:
                    return True
            return False

        return find_in_context(tree, v_norm)
