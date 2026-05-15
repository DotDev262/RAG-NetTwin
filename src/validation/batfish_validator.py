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
    from src.validation.batfish_validator import BatfishValidator

    validator = BatfishValidator()
    configs = {"Router-A": "interface Gig0/1\n ip address 192.168.1.1 255.255.255.0"}
    result = validator.validate(configs)
    print(result['status'])  # "PASS", "FAIL", "WARNING", or "SKIPPED"

Note:
    Batfish must be running (via Docker) for validation to work.
    If Batfish is unavailable, the validator returns SKIPPED status.
"""

import tempfile
import shutil
import json
import uuid
from pathlib import Path
from pybatfish.client.session import Session
from typing import Dict, Any

from src.validation.base import NetworkValidator
from src.config import settings
from src.utils import setup_logger
from src.utils import clean_cli_prose

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
    2. Detect vendor from src.config content (Cisco vs Juniper)
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
        """
        # Create a local session for thread safety (Pybatfish Sessions are not thread-safe)
        try:
            session = Session(host=self.host)
        except Exception as e:
            return {
                "status": "SKIPPED",
                "message": f"Could not connect to Batfish service: {e}",
            }

        # Generate unique network and snapshot names (Fix 2: Prevent state leakage)
        unique_id = str(uuid.uuid4())[:8]
        network_name = f"rag_net_{unique_id}"
        snapshot_name = f"snapshot_{unique_id}"

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
                if hostname is None:
                    hostname = "unnamed_device"

                safe_hostname = hostname.replace("/", "_").replace("\\", "_")

                # Robust Vendor Detection (Recommendation 2)
                # Check for Junos-specific 'set' or 'hierarchy' patterns
                is_juniper = (
                    any(
                        line.strip().startswith(
                            ("set ", "delete ", "edit ", "replace ", "show ")
                        )
                        for line in config_text.splitlines()
                    )
                    or "{" in config_text
                )

                # Force Juniper if it looks like Junos set commands
                if not is_juniper and "set protocols" in config_text.lower():
                    is_juniper = True

                header = "#\n" if is_juniper else "!\n"
                # Ensure the header is the VERY first thing in the file
                clean_lines = [
                    line for line in config_text.splitlines() if line.strip()
                ]

                if not clean_lines:
                    config_text = header
                else:
                    # Cisco Stabilization: Add 'end' if missing and not Juniper
                    if not is_juniper and clean_lines[-1].strip().lower() != "end":
                        clean_lines.append("end")

                    if not clean_lines[0].startswith(("#", "!")):
                        config_text = header + "\n".join(clean_lines)
                    else:
                        config_text = "\n".join(clean_lines)

                # Ensure trailing newlines (at least 2) to prevent Batfish EOF parser issues
                if not config_text.endswith("\n\n"):
                    config_text = config_text.rstrip() + "\n\n"

                if is_juniper:
                    safe_hostname = safe_hostname.replace(".cfg", "") + ".conf"
                elif not safe_hostname.endswith(".cfg"):
                    safe_hostname += ".cfg"

                with open(config_dir / safe_hostname, "w") as f:
                    f.write(config_text)

            # Step 2: Initialize Network and Snapshot in Batfish
            session.set_network(network_name)
            session.init_snapshot(temp_dir, name=snapshot_name, overwrite=True)

            # Step 3: Run Analysis Questions
            issues = []

            # Check for configuration parsing issues
            parse_status = session.q.initIssues().answer().frame()  # type: ignore
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
                    combined_text = (details + " " + line_text).lower()
                    if any(cmd.lower() in combined_text for cmd in self.known_gaps):
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
            undefined = session.q.undefinedReferences().answer().frame()  # type: ignore
            if not undefined.empty:
                for _, row in undefined.iterrows():
                    struct_type = str(row.get("Structure_Type", "Unknown"))
                    struct_name = str(row.get("Structure_Name", "Unknown"))
                    context = str(row.get("Context", ""))
                    line = str(row.get("Line", "unknown"))
                    filename = str(row.get("File_Name", "unknown"))

                    # Filter out useless 'Unknown' references that provide no signal
                    is_unknown = struct_type.lower() in [
                        "unknown",
                        "none",
                        "null",
                    ] and struct_name.lower() in ["unknown", "none", "null"]

                    has_no_context = not context or context.lower() in [
                        "unknown",
                        "none",
                        "null",
                    ]

                    if is_unknown and has_no_context:
                        continue

                    # Filter known noise (e.g., standard communities or defaults)
                    if (
                        struct_name in ["public", "private"]
                        and struct_type == "Community_List"
                    ):
                        continue

                    details = f"File {filename}: {struct_type} '{struct_name}' is referenced but not defined."
                    if context:
                        details += f" Context: {context}"
                    if line != "unknown":
                        details += f" at line: {line}"

                    issues.append(
                        {
                            "type": "UNDEFINED_REFERENCE",
                            "severity": "HIGH",
                            "details": details,
                        }
                    )

            # Add any empty config issues found earlier
            issues.extend(empty_issues)

            # Determine status based on issue types
            status = "PASS" if not issues else "FAIL"

            if issues:
                logger.info(f"Batfish Issues Found: {json.dumps(issues, indent=2)}")

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
            # Always clean up temporary directory and Batfish network (Fix 2)
            shutil.rmtree(temp_dir)
            if "session" in locals() and session:
                try:
                    session.delete_network(network_name)
                except Exception:
                    pass


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
