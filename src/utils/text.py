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
        "line ",
        "access-class ",
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


CLI_KEYWORD_ABBREVIATIONS = {
    r"\bint\b": "interface",
    r"\bip add\b": "ip address",
    r"\bsh\b": "show",
    r"\bconf t\b": "configure terminal",
    r"\bno shut\b": "no shutdown",
    r"\bdesc\b": "description",
    r"\bsw\b": "switchport",
    r"\bsw mode\b": "switchport mode",
    r"\bsw acc\b": "switchport access",
    r"\bsw tr\b": "switchport trunk",
}

CASE_SENSITIVE_PREFIXES = (
    "password",
    "secret",
    "community",
    "description",
    "banner",
    "key-string",
    "pre-shared-key",
)


def normalize_cli_command(line: str) -> str:
    """
    Normalizes a CLI command line:
    1. Strips leading/trailing whitespace and squashes multiple spaces.
    2. Expands common CLI abbreviations and aliases.
    3. Handles case-insensitivity appropriately for commands where OS syntax allows it,
       while preserving case-sensitive parameters (passwords, community strings, descriptions).
    """
    if not line:
        return ""

    # Squash spaces
    clean = re.sub(r"[ \t]+", " ", line.strip())

    # Check for case-sensitive segments
    lower = clean.lower()
    split_idx = -1
    for prefix in CASE_SENSITIVE_PREFIXES:
        match = re.search(rf"\b{prefix}\b", lower)
        if match:
            # We want to preserve case after the keyword
            split_idx = match.end()
            break

    if split_idx != -1:
        syntax_part = clean[:split_idx].lower()
        param_part = clean[split_idx:]
    else:
        syntax_part = clean.lower()
        param_part = ""

    # Expand abbreviations in syntax part
    for abbr_pat, full_kw in CLI_KEYWORD_ABBREVIATIONS.items():
        syntax_part = re.sub(abbr_pat, full_kw, syntax_part)

    # Recombine
    combined = (syntax_part + param_part).strip()
    return re.sub(r"[ \t]+", " ", combined)

