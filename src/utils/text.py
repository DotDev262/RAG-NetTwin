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
        "configure",
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
        "exit",
        "quit",
        "commit",
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
    )
    lower = line.lower()
    return lower.startswith(valid_starts)


def clean_cli_prose(text: str) -> str:
    """
    Extract valid network CLI commands from LLM output.
    """
    text = text.replace("<EOF>", "").replace("<end>", "").replace("[EOF]", "")
    text = text.replace("**", "").replace("```", "\n")
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
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
        )
        lower = line.lower()
        if any(lower.startswith(p) for p in prose_indicators):
            continue
        if line.replace(" ", "").replace("-", "").isdigit() or not any(
            c.isalpha() for c in line
        ):
            continue
        if _is_cli_command(line):
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)
