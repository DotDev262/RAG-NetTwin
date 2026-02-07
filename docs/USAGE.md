# Usage Guide

How to use RAG-NetTwin for generating network configurations.

## Table of Contents

1. [CLI Mode](#cli-mode)
2. [Web UI Mode](#web-ui-mode)
3. [Intent Format](#intent-format)
4. [Examples](#examples)
5. [Validation](#validation)
6. [Evaluation](#evaluation)

## CLI Mode

### Starting the CLI

```bash
# From project root
uv run python main.py

# Or activate venv first
source venv/bin/activate
python main.py
```

### Basic Usage

```
$ uv run python main.py
============================================================
 RAG-NetTwin: Hallucination-Mitigated Intent-Based Networking
============================================================

✓ LLM Provider: groq

Enter your network intent (or 'exit' to quit):
> Configure OSPF area 0 on Router-A interface Gig0/1 with IP 10.1.1.1/24

[1/3] Parsing Intent...
      ✓ Intent parsed: OSPF create

[2/3] Retrieving Documentation & Generating Config...

[3/3] Results:
----------------------------------------
Device: Router-A
Retrieved 15 references.

Generated Configuration:
```
! Based on [chunk_ios_ospf_001]
interface GigabitEthernet0/1
 ip address 10.1.1.1 255.255.255.0
 ip ospf 1 area 0
 no shutdown
!
router ospf 1
 router-id 10.1.1.1
!
```
----------------------------------------

Enter your network intent (or 'exit' to quit):
> exit
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `exit`, `quit`, `q` | Exit the application |
| `help` | Show help message |
| `clear` | Clear screen |

## Web UI Mode

### Starting the Web Interface

```bash
# Start backend server
uv run python ui/backend/main.py

# Server will start on http://localhost:5000
```

### Web UI Features

- **Intent Input:** Natural language text area
- **Device Selection:** Vendor, OS, version dropdowns
- **Configuration Preview:** Syntax-highlighted output
- **Validation Results:** Pass/fail status per tier
- **Download Config:** Export as .txt or .json

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/parse` | POST | Parse natural language intent |
| `/api/generate` | POST | Generate configuration |
| `/api/validate` | POST | Run validation tiers |
| `/api/evaluate` | POST | Run evaluation benchmark |

**Example API Call:**

```bash
curl -X POST http://localhost:5000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "Configure OSPF area 0 on Router-A",
    "device": {
      "name": "Router-A",
      "vendor": "cisco",
      "os_type": "ios-xe",
      "os_version": "17.6"
    }
  }'
```

## Intent Format

### Natural Language Intents

RAG-NetTwin understands various natural language patterns:

**Basic Structure:**
```
<Action> <Protocol> <Parameters> on <Device>
```

**Examples:**

```
# OSPF Configuration
"Configure OSPF process 1 area 0 on Router-A"
"Enable OSPF on Gig0/1 with IP 10.1.1.1/24"

# BGP Configuration
"Setup BGP AS 65001 with neighbor 10.1.1.2"
"Configure BGP peering with AS 65002"

# ACL Configuration
"Create ACL named WEB_FILTER to block port 80"
"Deny all traffic from 192.168.1.0/24"

# Interface Configuration
"Configure interface Gig0/1 with IP 10.1.1.1/30"
"Set description on Gig0/2 to Link-to-Core"

# VLAN Configuration
"Create VLAN 100 named MANAGEMENT"
"Assign ports Gi0/1-4 to VLAN 100"
```

### Structured Intent Format

If you prefer structured input, use JSON:

```json
{
  "protocol": "OSPF",
  "action": "create",
  "devices": [
    {
      "name": "Router-A",
      "vendor": "cisco",
      "os_type": "ios-xe",
      "os_version": "17.6"
    }
  ],
  "parameters": {
    "process_id": "1",
    "area": "0",
    "interface": "Gig0/1",
    "ip": "10.1.1.1/24"
  },
  "requirements": ["establish_adjacency", "advertise_network"]
}
```

## Examples

### Example 1: OSPF Configuration

**Input:**
```
Configure OSPF process 1 area 0 on Router-A. Enable on interface Gig0/1 with IP 10.1.1.1/24.
Device: Cisco IOS-XE 17.6
```

**Generated Output:**
```ios
! Based on [chunk_ios_ospf_001]
interface GigabitEthernet0/1
 description OSPF Backbone Link
 ip address 10.1.1.1 255.255.255.0
 ip ospf 1 area 0
 no shutdown
!
! Based on [chunk_ios_ospf_002]
router ospf 1
 router-id 10.1.1.1
 network 10.1.1.0 0.0.0.255 area 0
!
```

### Example 2: Access Control List

**Input:**
```
Create an ACL named BLOCK_WEB to deny HTTP traffic (TCP port 80) from any source to any destination on Router-B.
Device: Cisco IOS-XE 17.6
```

**Generated Output:**
```ios
! Based on [chunk_ios_acl_001]
ip access-list extended BLOCK_WEB
 deny tcp any any eq 80
 permit ip any any
!
! Based on [chunk_ios_acl_002]
interface GigabitEthernet0/0
 ip access-group BLOCK_WEB in
!
```

### Example 3: BGP Configuration

**Input:**
```
Configure BGP AS 65001 with neighbor 192.168.1.2 in AS 65002. Advertise network 10.0.0.0/8 on Router-C.
Device: Cisco IOS-XE 17.6
```

**Generated Output:**
```ios
! Based on [chunk_ios_bgp_001]
router bgp 65001
 bgp router-id 192.168.1.1
 neighbor 192.168.1.2 remote-as 65002
 neighbor 192.168.1.2 description Peer-to-AS65002
 !
 address-family ipv4
  network 10.0.0.0 mask 255.0.0.0
  neighbor 192.168.1.2 activate
 exit-address-family
!
```

### Example 4: Multiple Devices

**Input:**
```
Configure OSPF area 0 on Router-A (Cisco IOS-XE 17.6) and Router-B (Juniper JunOS 21.4). Both have interface IP 10.1.1.x/24.
```

**Generated Output:**

Router-A (Cisco):
```ios
interface GigabitEthernet0/1
 ip address 10.1.1.1 255.255.255.0
 ip ospf 1 area 0
!
router ospf 1
 router-id 10.1.1.1
!
```

Router-B (Juniper):
```junos
interfaces {
    ge-0/0/1 {
        unit 0 {
            family inet {
                address 10.1.1.2/24;
            }
        }
    }
}
protocols {
    ospf {
        area 0.0.0.0 {
            interface ge-0/0/1.0;
        }
    }
}
```

## Validation

### Running Validation

Validation is automatically performed after generation if validators are installed.

**Manual Validation:**

```bash
# Run specific validation tier
python -c "
from validation.batfish_validator import BatfishValidator
validator = BatfishValidator()
result = validator.validate(config_text='your_config_here')
print(result)
"
```

### Validation Output

```json
{
  "tier": 1,
  "validator": "batfish",
  "passed": false,
  "errors": [
    {
      "type": "syntax",
      "line": 5,
      "message": "Invalid command: ip ospf 1 area",
      "suggestion": "Did you mean: ip ospf 1 area 0?"
    }
  ],
  "warnings": [],
  "timestamp": "2025-02-08T10:30:00Z"
}
```

### Validation Levels

**Tier 1 (Static):**
- Command syntax validation
- Logical consistency checks
- Policy compliance

**Tier 2 (Emulation):**
- Protocol state verification
- Neighbor adjacency testing
- Configuration deployment test

**Tier 3 (Simulation):**
- Traffic flow testing
- Performance benchmarking
- Edge case validation

## Evaluation

### Running Benchmarks

```bash
# Run evaluation with test scenarios
uv run python src/evaluation/evaluator.py
```

### Evaluation Metrics

**Baseline (Vanilla LLM) vs RAG:**

| Metric | Vanilla LLM | RAG-NetTwin |
|--------|-------------|-------------|
| Hallucination Rate | ~25% | < 2% |
| Syntactic Accuracy | ~85% | > 99% |
| Semantic Correctness | ~75% | > 95% |
| Generation Time | ~2s | ~5s |

### Custom Benchmarks

```python
from evaluation.evaluator import Evaluator

evaluator = Evaluator()

# Define test scenarios
scenarios = [
    "Configure OSPF area 0 on Router-A",
    "Create ACL to block port 80",
    "Setup BGP AS 65001"
]

# Run evaluation
evaluator.run_benchmark(scenarios, output_file="results/my_benchmark.json")
```

### Interpreting Results

```json
{
  "scenario": "Configure OSPF area 0",
  "baseline": {
    "config": "...",
    "time_sec": 2.1,
    "hallucination_score": 0.25
  },
  "rag": {
    "config": "...",
    "retrieved_sources": ["chunk_001", "chunk_002"],
    "time_sec": 5.3,
    "hallucination_score": 0.02
  }
}
```

**Score Interpretation:**
- `hallucination_score`: 0.0 = perfect, 1.0 = completely hallucinated
- `time_sec`: Generation time in seconds
- `retrieved_sources`: Documentation chunks used

## Best Practices

### 1. Be Specific

**❌ Vague:**
```
Configure OSPF on the router.
```

**✅ Specific:**
```
Configure OSPF process 1 area 0 on Router-A interface Gig0/1 with IP 10.1.1.1/24.
```

### 2. Include Device Details

**❌ Missing Details:**
```
Setup BGP.
```

**✅ With Details:**
```
Configure BGP AS 65001 on Router-A (Cisco IOS-XE 17.6) with neighbor 10.1.1.2 in AS 65002.
```

### 3. One Intent at a Time

**❌ Complex:**
```
Configure OSPF, BGP, and ACLs on Router-A.
```

**✅ Focused:**
```
Configure OSPF area 0 on Router-A.
```

### 4. Validate Before Deployment

Always run validation:
```bash
# Check with Batfish
systemctl status batfish

# Verify output
python src/validation/batfish_validator.py
```

### 5. Review Generated Configs

Always review before applying:
- Check for correct IP addresses
- Verify interface names
- Confirm OS version-specific syntax

## Troubleshooting

**Config not generated?**
- Check API key in .env
- Verify vector database is populated
- Check LLM provider status

**Validation fails?**
- Verify validators are installed: `sudo ./scripts/install_validators_ubuntu.sh --verify`
- Check service status: `systemctl status batfish gns3-server`

**Slow generation?**
- Groq is faster than Gemini for this use case
- Check internet connection
- Verify vector DB is local (not remote)

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

**Next:** [API Reference](API.md) | [Configuration](CONFIGURATION.md) | [Troubleshooting](TROUBLESHOOTING.md)
