
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from evaluation.hallucination_detector import HallucinationDetector
import re

def debug():
    configs = [
        "set firewall filter discard_icmp term 1 then discard",
        "set firewall filter discard_icmp term 1 from source-address 10.0.0.0/8",
        "set firewall filter discard_icmp term 1 from protocol icmp"
    ]
    
    NOISY = ["no", "set", "exit", "end", "quit", "commit", "logging", "snmp", "line", "vty", "banner",
                 "enable", "configure", "terminal", "firewall", "filter", "term", "protocols", "interfaces", "system"]
        
    COMMON_VERBS = ["interface", "router", "ip", "ipv6", "vlan", "access-list", "set", "show", "crypto", "policy", "tunnel", "route", "address", 
                    "ospf", "bgp", "switchport", "neighbor", "snmp-server", "username", "hostname", "description", "logging", "system",
                    "remote-as", "area", "permit", "deny", "tcp", "any", "timers", "hello-interval", "network", "mask",
                    "firewall", "filter", "term", "protocol", "family", "inet", "standard", "extended", "privilege", "snmp", "community",
                    "mode", "trunk", "allowed", "from", "to", "then", "discard", "accept", "source-address", "destination-address", 
                    "in", "out", "access-group", "access-class", "peer-as", "group", "external", "local-address"]
    
    intent = "Configure a firewall filter on Juniper to discard ICMP traffic from 10.0.0.0/8"

    for config in configs:
        print(f"\n--- Testing: {config} ---")
        parts = config.split()
        structural_tokens = []
        for word in parts:
            w_lower = word.lower().rstrip(":")
            is_keyword = w_lower in ["vlan", "ospf", "bgp", "router", "interface", "set", "protocols", "mode", "type", "group", "area", "route", "address", "switchport", "neighbor"]
            is_numeric_ip = re.match(r'^[0-9.:/a-fA-F]+$', word) is not None and (any(c.isdigit() for c in word) or "::" in word)
            is_interface = re.match(r'^[a-zA-Z]+[0-9/.]+$', word) is not None
            is_user_id = ((any(c.isdigit() for c in word) and any(c in word for c in "-_.")) or (word.isupper() and len(word) > 3)) and not is_keyword
            is_in_intent = (len(w_lower) > 2 and w_lower in intent.lower() and not is_keyword)
            
            print(f"Word: {word} | is_numeric_ip: {is_numeric_ip}, is_interface: {is_interface}, is_user_id: {is_user_id}, is_in_intent: {is_in_intent}")
            
            if is_numeric_ip or is_interface or is_user_id or is_in_intent:
                continue
            if w_lower in NOISY:
                continue
            structural_tokens.append(w_lower)
        
        print(f"Structural tokens: {structural_tokens}")
        
        # Grounding check simulation
        full_doc_text = "some doc text" # simulate empty doc text to see if all tokens are in COMMON_VERBS
        all_tokens_grounded = True
        for token in structural_tokens:
            if token not in full_doc_text and len(token) > 3 and token not in COMMON_VERBS:
                all_tokens_grounded = False
                print(f"UNGROUNDED TOKEN: {token}")
                break
        
        if not all_tokens_grounded:
            print("Status: UNGROUNDED (token missing)")
            continue

        if len(structural_tokens) >= 2:
            primary = structural_tokens[0]
            secondary = structural_tokens[1]
            if primary in COMMON_VERBS and secondary not in COMMON_VERBS:
                prefix = f"{primary} {secondary}"
                if prefix not in full_doc_text and secondary not in full_doc_text:
                    print(f"Status: UNGROUNDED (sequence missing) - Prefix: {prefix}")
            else:
                print("Status: GROUNDED")
        else:
             print("Status: GROUNDED")

if __name__ == "__main__":
    debug()
