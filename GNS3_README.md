# GNS3 Digital Twin Emulation Setup Guide

This document describes the environment setup and virtual machine template requirements for running the Tier 3 Emulation validation loop of the **RAG-NetTwin** framework.

---

## 1. GNS3 Template Requirements

The [GNS3Validator](file:///home/aryan/Projects/RAG-NetTwin/src/validation/gns3_validator.py#L40) dynamically provisions virtualized network topologies. To ensure correct mapping of L2 and L3 configurations to appropriate firmware images, you must define the following templates in your GNS3 server:

### A. Cisco IOS / IOL (default L3 router image)
* **Required Template Name**: Must contain one of: `router`, `iosv`, `csr1000v`, `viou`, `iol`, or `cisco`.
* **Recommended Image**: Cisco IOSv (vios-adventerprisek9-m.vmdk.SPA.156-2.T) or Cisco IOL L3 (i86bi_linux-adventerprisek9-ms.bin).
* **Firmware Version**: Mapped to version `15.6` or `17.6`.

### B. Cisco L2 Switch (default L2 switch image)
* **Required Template Name**: Must contain one of: `iosvl2`, `switch`, `l2`, `viou-l2`, `iol-l2`, or `cisco`.
* **Recommended Image**: Cisco IOSvL2 (vios_l2-adventerprisek9-m.03.2017.qcow2) or Cisco IOL L2 (i86bi_linux_l2-adventerprisek9-ms.bin).
* **Firmware Version**: Mapped to version `15.2` or `15.8(3)M`.

### C. Juniper / VyOS (default Juniper simulation)
* **Required Template Name**: Must contain one of: `junos`, `vsrx`, `vmx`, `olive`, `juniper`, or `vyos`.
* **Recommended Image**: VyOS 1.3/1.4 or Juniper vSRX.

---

## 2. API Authentication Configuration

The [GNS3Validator](file:///home/aryan/Projects/RAG-NetTwin/src/validation/gns3_validator.py#L40) uses the GNS3 HTTP REST API to control nodes and links. Credentials must be supplied via environment variables to avoid hardcoded secrets:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set the variables:
   ```bash
   export GNS3_USERNAME="your_gns3_username"
   export GNS3_PASSWORD="your_gns3_password"
   ```

---

## 3. Running Emulation Validation

To run the full paper evaluation including the GNS3 hardware testbed:
```bash
uv run python run_paper_eval.py --run-gns3
```
If a command fails to parse or execute on the device, it will be flagged, and the **Config Acceptance Rate (CAR)** will register a failure.
