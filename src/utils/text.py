import re


def _is_cli_command(line: str) -> bool:
    """
    Check if a line looks like a valid network CLI command.
    """
    valid_starts = (
        "interface",
        "router",
        "ip ",
        "ipv6 ",
        "no ",
        "description",
        "set ",
        "policy-options",
        "routing-options",
        "protocols",
        "system",
        "snmp",
        "logging",
        "ntp",
        "user",
        "username",
        "access-list",
        "!",
        "quit",
        "apply",
        "firewall",
        "vlan",
        "spanning-tree",
        "area ",
        "network ",
        "neighbor ",
        "address-family",
        "route-map",
        "prefix-list",
        "hostname ",
        "banner ",
        "term ",
        "from ",
        "then ",
        "edit ",
        "family ",
        "ssh ",
        "lldp",
        "cdp",
        "class-map",
        "policy-map",
        "service-policy",
        "priority",
        "bandwidth",
        "fair-queue",
        "shape",
        "route-target",
        "extcommunity",
        "address ",
        "mask ",
        "mask-src ",
        "src-packet",
        "distribute ",
        "redistribute",
        "switchport",
        "crypto",
        "isakmp",
        "ipsec",
        "vrrp",
        "flow",
        "monitor",
        "exporter",
        "record",
        "collect",
        "counter",
        "bytes",
        "packets",
        "prefix",
        "input",
        "output",
        "timestamp",
        "authentication",
        "nat",
        "inside",
        "outside",
        "pool",
        "dscp",
        "cs6",
        "orlonger",
        "transport",
        "udp",
        "ipfix",
        "version",
        "sys-uptime",
        "first",
        "last",
        "restrict",
        "console",
        "login",
        "default",
        "nonegotiate",
        "auto",
        "qos",
        "voip",
        "mls",
        "trust",
        "cos",
        "map",
        "method",
        "algorithm",
        "establish-tunnels",
        "immediately",
        "bind-interface",
        "security",
        "ike",
        "proposal",
        "gateway",
        "vpn",
        "bind-interface",
        "external-interface",
        "perfect-forward-secrecy",
        "keys",
        "df-bit",
        "copy",
        "precedence",
        "percent",
        "track",
        "longer",
        "encapsulation",
        "dot1q",
        "flow-cache",
        "timeout",
        "active",
        "inactive",
        "ingress",
        "egress",
        "zone",
        "untrust",
    )
    lower = line.lower()
    return lower.startswith(valid_starts)


def clean_cli_prose(text: str) -> str:
    """
    Extract valid network CLI commands from LLM output.
    """
    # Pre-cleaning: strip EOF tokens (case-insensitive) and markdown
    # Use aggressive regex for various end-of-config markers
    text = re.sub(r"(?i)\s*[\[<](EOF|end|DONE|STOP)[\]>]\s*", "\n", text)
    text = text.replace("**", "").replace("```", "\n")

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Strip common markdown bullets/numbering from the start
        line = re.sub(r"^[\s\t•*-]*(\d+\.)?[\s\t]*", "", line).strip()

        if not line or line.startswith("#"):
            continue

        if line in ("*", "-", "|", "---", "***"):
            continue

        prose_indicators = (
            "here is",
            "this command",
            "following",
            "example",
            "output:",
            "result:",
            "note:",
            "note that",
            "cisco cli:",
            "juniper cli:",
        )
        lower = line.lower()
        if any(lower.startswith(p) for p in prose_indicators):
            continue

        # Filter out lines that are just numbers or non-alphabetic
        if line.replace(" ", "").replace("-", "").isdigit() or not any(
            c.isalpha() for c in line
        ):
            continue

        if _is_cli_command(line):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
