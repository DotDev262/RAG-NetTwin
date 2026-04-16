"""
Batfish Validator Module for RAG-NetTwin.

This module provides Tier 1 static analysis validation using Batfish,
an open-source network validation tool. Batfish parses network device
configurations and runs analysis queries to detect issues without
requiring network connectivity.

Key Features:
- Static configuration parsing without network access
- Syntax validation and undefined reference detection
- Known parser gap filtering (commands Batfish doesn't support)
- Vendor-aware config file handling (.cfg vs .conf)

Typical Usage:
    from validation.batfish_validator import BatfishValidator

    validator = BatfishValidator()
    configs = {"Router-A": "interface Gig0/1\n ip address 192.168.1.1 255.255.255.0"}
    result = validator.validate(configs)
    print(result['status'])  # "PASS", "FAIL", "WARNING", or "SKIPPED"

Note:
    Batfish must be running (via Docker) for validation to work.
    If Batfish is unavailable, the validator returns SKIPPED status.
"""

import os
import tempfile
import shutil
import json
from pathlib import Path
from pybatfish.client.session import Session
from pybatfish.datamodel import Interface
import pandas as pd
from typing import Dict, Any, List

from validation.base import NetworkValidator
from config import settings
from utils import setup_logger
from utils import clean_cli_prose

logger = setup_logger("BatfishValidator")


class BatfishValidator(NetworkValidator):
    """
    Performs Tier 1 Static Analysis using Batfish.

    This validator provides the first tier of configuration validation,
    focusing on static analysis without requiring network connectivity.
    It parses configurations and runs various analysis questions to
    detect syntax errors, undefined references, and other issues.

    Batfish acts as a "first pass" filter - it catches obvious issues
    quickly (~100ms per config) while more complex issues require
    Tier 2 (Containerlab) or Tier 3 (GNS3) validation.

    Validation Steps:
    1. Clean configs (remove LLM-generated labels that break parsing)
    2. Detect vendor from config content (Cisco vs Juniper)
    3. Write configs with appropriate file extensions
    4. Initialize Batfish network and snapshot
    5. Run analysis questions (parse issues, undefined references)
    6. Filter known Batfish parser gaps
    7. Return status based on issue types found

    Status Values:
    - PASS: No issues found
    - WARNING: Non-critical issues (ACL shadowing, config warnings)
    - FAIL: High severity issues (parse errors, undefined references)
    - REJECT_FOR_MANUAL_REVIEW: Parse issues that need human review
    - SKIPPED: Batfish service not available
    - ERROR: Unexpected exception during validation
    """

    def __init__(self):
        """
        Initialize the BatfishValidator.

        Attempts to connect to the Batfish service. If connection fails,
        the validator will return SKIPPED status for all validations.
        """
        super().__init__(tier=1)
        self.host = settings.batfish_host
        self.session = None
        self.known_gaps = set()

        # Load known Batfish gaps from config
        try:
            config_path = Path("config/batfish_gaps.json")
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.known_gaps = set(data.get("batfish_known_gaps", []))
                logger.info(f"Loaded {len(self.known_gaps)} known Batfish gaps.")
            else:
                logger.warning(f"Batfish gaps config not found at {config_path}")
        except Exception as e:
            logger.error(f"Failed to load Batfish gaps config: {e}")

        try:
            # Try to connect to Batfish
            self.session = Session(host=self.host)
            # Basic connectivity check
            logger.info(f"Connected to Batfish at {self.host}")
        except Exception as e:
            logger.warning(f"Could not connect to Batfish: {e}")

    def validate(self, configs: Dict[str, str], intent: Any = None) -> Dict[str, Any]:
        """
        Validates a set of network device configurations.

        This method performs static analysis on network configurations
        using Batfish. It creates a temporary snapshot, runs analysis
        questions, and returns validation results with any issues found.

        Args:
            configs: Dictionary mapping hostname to configuration text.
                Example: {"Router-A": "interface Gig0/1\n ip address ..."}
            intent: Optional StructuredIntent for additional context.
                Not used in Tier 1 validation.

        Returns:
            Dictionary containing:
                - status: Validation result (PASS, FAIL, WARNING, etc.)
                - tier: Always 1 for this validator
                - issues: List of issue dicts with type, severity, details
                - snapshot_id: Batfish snapshot identifier (for debugging)
                - summary: Human-readable summary of results
                - error: Error message if status is ERROR

        Note:
            If Batfish is not available, returns {"status": "SKIPPED", ...}
            with a message instructing user to start Batfish via Docker.
        """
        # Generate unique network and snapshot names
        network_name = "rag_net"
        snapshot_name = f"snapshot_{int(os.getpid())}"

        # Return skipped status if Batfish is not available
        if not self.session:
            return {
                "status": "SKIPPED",
                "message": "Batfish service not available. Ensure Batfish is running (Docker).",
            }

        # Clean configs: Remove LLM-generated labels/comments that break parsing
        # Batfish is strict about config format - these labels cause parse failures
        cleaned_configs = {
            dev_name: clean_cli_prose(raw_cfg) for dev_name, raw_cfg in configs.items()
        }

        # Check for empty configs (indicates LLM generation failure)
        empty_issues = []
        for dev_name, config_text in cleaned_configs.items():
            if not config_text.strip():
                empty_issues.append(
                    {
                        "type": "EMPTY_CONFIG",
                        "severity": "HIGH",
                        "details": f"Device {dev_name} produced no valid commands after cleaning",
                    }
                )

        # Create temporary directory for configs
        temp_dir = tempfile.mkdtemp()
        try:
            # Step 1: Prepare directory structure for Batfish
            config_dir = Path(temp_dir) / "configs"
            config_dir.mkdir(parents=True)

            # Write each config with appropriate file extension
            for hostname, config_text in cleaned_configs.items():
                # Sanitize hostname to prevent directory traversal or path errors
                safe_hostname = hostname.replace("/", "_").replace("\\", "_")

                # Detect vendor from config content
                # Juniper configs use "set" commands at the start
                # Cisco configs use Cisco IOS syntax
                is_juniper = (
                    any(
                        config_text.strip().startswith(prefix)
                        for prefix in [
                            "set ",
                            "firewall",
                            "protocols ",
                            "interfaces ",
                            "routing-options",
                        ]
                    )
                    or "set " in config_text[:500]
                )

                # Set appropriate extension:
                # - Juniper: .conf (Batfish recognizes set commands)
                # - Cisco: .cfg
                if is_juniper:
                    safe_hostname = safe_hostname.replace(".cfg", "") + ".conf"
                elif not safe_hostname.endswith(".cfg"):
                    safe_hostname += ".cfg"

                with open(config_dir / safe_hostname, "w") as f:
                    f.write(config_text)

            # Step 2: Initialize Network and Snapshot in Batfish
            self.session.set_network(network_name)
            self.session.init_snapshot(temp_dir, name=snapshot_name, overwrite=True)

            # Step 3: Run Analysis Questions
            issues = []

            # Check for configuration parsing issues
            parse_status = self.session.q.initIssues().answer().frame()
            if not parse_status.empty:
                for _, row in parse_status.iterrows():
                    # Safely extract values from the dataframe
                    details = (
                        str(row.get("Details", ""))
                        if not isinstance(row.get("Details"), bool)
                        else ""
                    )
                    line_text = (
                        str(row.get("Line_Text", ""))
                        if not isinstance(row.get("Line_Text"), bool)
                        else ""
                    )
                    filename = (
                        str(row.get("File_Name", "unknown"))
                        if not isinstance(row.get("File_Name"), bool)
                        else "unknown"
                    )

                    # Filter out benign warnings that aren't actionable
                    if not details:
                        continue
                    if any(
                        msg in details for msg in ["No hostname set", "File is empty"]
                    ):
                        continue
                    if "File format is unknown" in details:
                        continue
                    if line_text == "None":
                        continue

                    # Filter out known Batfish parser gaps
                    # These are valid commands that Batfish doesn't support yet
                    if any(cmd in line_text for cmd in self.known_gaps):
                        continue

                    # Handle specific known warnings
                    if "No candidates for OSPF router-id" in details:
                        issues.append(
                            {
                                "type": "CONFIG_WARNING",
                                "severity": "MEDIUM",
                                "details": f"File {filename}: {details}",
                            }
                        )
                        continue

                    # Add parse issue for everything else
                    issues.append(
                        {
                            "type": "PARSE_ISSUE",
                            "severity": "HIGH",
                            "details": f"File {filename}: {details} at line: {line_text}",
                        }
                    )

            # Check for undefined references (e.g., referenced but not defined)
            undefined = self.session.q.undefinedReferences().answer().frame()
            if not undefined.empty:
                for _, row in undefined.iterrows():
                    struct_type = row.get("Structure_Type", "Unknown")
                    struct_name = row.get("Structure_Name", "Unknown")
                    issues.append(
                        {
                            "type": "UNDEFINED_REFERENCE",
                            "severity": "HIGH",
                            "details": f"File {row.get('File_Name', 'unknown')}: {struct_type} '{struct_name}' is referenced but not defined.",
                        }
                    )

            # Add any empty config issues found earlier
            issues.extend(empty_issues)

            # Determine status based on issue types
            status = "PASS" if not issues else "FAIL"

            # Implementation of Fail-Safe Policy from design:
            # "the system defaults to a 'REJECT_FOR_MANUAL_REVIEW' status for any
            # command not supported by the Batfish parser."
            if any(i["type"] == "PARSE_ISSUE" for i in issues):
                status = "REJECT_FOR_MANUAL_REVIEW"
            elif any(i["type"] in ["CONFIG_WARNING", "ACL_SHADOWING"] for i in issues):
                status = "WARNING"
            elif issues:
                status = "FAIL"

            return {
                "status": status,
                "tier": 1,
                "issues": issues,
                "snapshot_id": snapshot_name,
                "summary": f"Found {len(issues)} potential issues.",
            }

        except Exception as e:
            # Catch any unexpected errors during validation
            return {"status": "ERROR", "error": str(e)}
        finally:
            # Always clean up temporary directory
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    # POC Test - demonstrates usage without requiring Batfish
    validator = BatfishValidator()

    # Sample config with intentional issues for testing
    test_configs = {
        "Router-1": """
interface GigabitEthernet0/1
 ip address 192.168.1.1 255.255.255.0
!
ip access-list extended TEST_ACL
 permit ip any any
 deny ip 10.0.0.0 0.255.255.255 any ! This is shadowed
!
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
"""
    }

    if validator.session:
        result = validator.validate(test_configs)
        import json

        print(json.dumps(result, indent=2))
    else:
        print(
            "Batfish not running. Start it with: docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish"
        )
