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
            used_route_maps: set[str] = set()
            defined_route_maps: set[str] = set()
            # 2. ACL checks
            used_acls: set[str] = set()
            defined_acls: set[str] = set()
            # 3. Policy-map checks
            used_policies: set[str] = set()
            defined_policies: set[str] = set()

            for line in lines:
                l_strip = line.strip()
                # Definitions
                rm_def = re.match(r"^route-map\s+([^\s]+)", l_strip)
                if rm_def:
                    defined_route_maps.add(rm_def.group(1))

                acl_def = re.match(
                    r"^(?:ip\s+)?access-list\s+(?:extended\s+|standard\s+)?([^\s]+)",
                    l_strip,
                )
                if acl_def:
                    defined_acls.add(acl_def.group(1))

                # Handle old-style standard/extended ACLs (e.g. access-list 101 permit...)
                old_acl_def = re.match(r"^access-list\s+([0-9]+)\s+", l_strip)
                if old_acl_def:
                    defined_acls.add(old_acl_def.group(1))

                pol_def = re.match(r"^policy-map\s+([^\s]+)", l_strip)
                if pol_def:
                    defined_policies.add(pol_def.group(1))

                # Usages
                rm_use = re.search(r"route-map\s+([^\s!]+)", line)
                if rm_use and not l_strip.startswith("route-map"):
                    used_route_maps.add(rm_use.group(1))

                acl_use = re.search(r"access-group\s+([^\s]+)", line)
                if acl_use:
                    used_acls.add(acl_use.group(1))

                pol_use = re.search(
                    r"service-policy\s+(?:input|output)\s+([^\s]+)", line
                )
                if pol_use:
                    used_policies.add(pol_use.group(1))

                nat_list_use = re.search(
                    r"ip\s+nat\s+inside\s+source\s+list\s+([^\s]+)", line
                )
                if nat_list_use:
                    used_acls.add(nat_list_use.group(1))  # NAT list is an ACL

                # BGP neighbor peer-group or route-map usages
                bgp_rm_use = re.search(
                    r"neighbor\s+[^\s]+\s+route-map\s+([^\s]+)", line
                )
                if bgp_rm_use:
                    used_route_maps.add(bgp_rm_use.group(1))

            for rm in used_route_maps:
                if rm not in defined_route_maps:
                    issues.append(
                        f"Cisco Error: Route-map '{rm}' is referenced but not defined."
                    )

            for acl in used_acls:
                if acl not in defined_acls:
                    # Ignore common standard ACL numbers if they look like they might be built-in
                    if not (acl.isdigit() and int(acl) < 100):
                        issues.append(
                            f"Cisco Warning: Access-group/List '{acl}' is referenced but not defined."
                        )

            for pol in used_policies:
                if pol not in defined_policies:
                    issues.append(
                        f"Cisco Error: Policy-map '{pol}' is referenced but not defined."
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
