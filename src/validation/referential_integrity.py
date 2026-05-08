import re
from typing import List


class ReferentialIntegrityValidator:
    """
    Checks for broken references in generated network configurations.
    Example: referencing a route-map that isn't defined in the config.
    """

    @staticmethod
    def check_config(config: str, vendor: str = "cisco") -> List[str]:
        """
        Scans config for missing definitions.
        Returns a list of error/warning messages.
        """
        issues = []
        vendor = vendor.lower()
        lines = config.splitlines()

        if vendor == "cisco":
            # 1. Route-map checks
            used_route_maps = set()
            defined_route_maps = set()
            for line in lines:
                # Definition
                rm_def = re.match(r"^route-map\s+([^\s]+)", line.strip())
                if rm_def:
                    defined_route_maps.add(rm_def.group(1))

                # Usage
                rm_use = re.search(r"route-map\s+([^\s!]+)", line)
                if rm_use and not line.strip().startswith("route-map"):
                    used_route_maps.add(rm_use.group(1))

            for rm in used_route_maps:
                if rm not in defined_route_maps:
                    issues.append(
                        f"Cisco Error: Route-map '{rm}' is referenced but not defined."
                    )

            # 2. ACL checks (Simplified)
            used_acls = set()
            defined_acls = set()
            for line in lines:
                acl_def = re.match(
                    r"^(?:ip\s+)?access-list\s+(?:extended\s+|standard\s+)?([^\s]+)",
                    line.strip(),
                )
                if acl_def:
                    defined_acls.add(acl_def.group(1))

                acl_use = re.search(r"access-group\s+([^\s]+)", line)
                if acl_use:
                    used_acls.add(acl_use.group(1))

            for acl in used_acls:
                if acl not in defined_acls:
                    # Some built-in ACLs or numbers might exist, but usually failure is likely
                    issues.append(
                        f"Cisco Warning: Access-group '{acl}' is referenced; verify definition exists."
                    )

        elif vendor == "juniper":
            # Juniper uses policy-statements and filters
            used_policies = set()
            defined_policies = set()
            for line in lines:
                # set policy-options policy-statement XYZ ...
                p_def = re.search(r"policy-statement\s+([^\s]+)", line)
                if p_def and "set policy-options" in line:
                    defined_policies.add(p_def.group(1))

                # set protocols bgp group X export XYZ
                p_use = re.search(r"(?:import|export|policy)\s+([^\s]+)", line)
                if p_use and "policy-statement" not in line:
                    used_policies.add(p_use.group(1))

            for p in used_policies:
                if p not in defined_policies:
                    # Ignore common built-ins if any
                    issues.append(
                        f"Juniper Warning: Policy '{p}' is referenced but not defined in this block."
                    )

        return issues
