import os
import tempfile
import shutil
from pathlib import Path
from pybatfish.client.session import Session
from pybatfish.datamodel import Interface
import pandas as pd
from typing import Dict, Any, List

from validation.base import NetworkValidator
from config import settings


class BatfishValidator(NetworkValidator):
    """Performs Tier 1 Static Analysis using Batfish."""

    def __init__(self):
        super().__init__(tier=1)
        self.host = settings.batfish_host
        self.session = None

        try:
            self.session = Session(host=self.host)
            # Basic connectivity check
            print(f"Connected to Batfish at {self.host}")
        except Exception as e:
            print(f"Warning: Could not connect to Batfish: {e}")

    def validate(self, configs: Dict[str, str], intent: Any = None) -> Dict[str, Any]:
        """
        Validates a set of configurations.
        configs: Mapping of hostname to config text.
        """
        network_name = "rag_net"
        snapshot_name = f"snapshot_{int(os.getpid())}"

        if not self.session:
            return {
                "status": "SKIPPED",
                "message": "Batfish service not available. Ensure Batfish is running (Docker).",
            }

        # --- FINAL CLEANUP: Remove LLM labels that break Batfish ---
        cleaned_configs = {}
        for dev_name, raw_cfg in configs.items():
            lines = raw_cfg.split("\n")
            cleaned_lines = []
            for line in lines:
                clean_line = line
                # Remove common prefixes like "Assistant:", "CLI:", etc.
                if ":" in line[:15]: 
                    prefix = line.split(":")[0].strip().lower()
                    if prefix in ["assistant", "cli", "config", "device", "note", "sure", "system"]:
                        clean_line = line.split(":", 1)[1].strip()
                
                # Filter out lines that are clearly prose (many words, no special chars)
                words = clean_line.split()
                if clean_line and len(words) < 12: 
                    cleaned_lines.append(clean_line)
            
            cleaned_configs[dev_name] = "\n".join(cleaned_lines).strip()
        # ----------------------------------------------------------

        temp_dir = tempfile.mkdtemp()
        try:
            # 1. Prepare directory structure for Batfish
            config_dir = Path(temp_dir) / "configs"
            config_dir.mkdir(parents=True)

            for hostname, config_text in cleaned_configs.items():
                with open(config_dir / hostname, "w") as f:
                    f.write(config_text)

            # 2. Initialize Network and Snapshot
            self.session.set_network(network_name)
            self.session.init_snapshot(temp_dir, name=snapshot_name, overwrite=True)

            # 3. Run Analysis Questions
            issues = []

            # Check for configuration errors (e.g., syntax-related)
            parse_status = self.session.q.initIssues().answer().frame()
            if not parse_status.empty:
                for _, row in parse_status.iterrows():
                    details = str(row.get("Details", ""))
                    line_text = str(row.get("Line_Text", ""))
                    
                    # Filter out common benign warnings
                    if any(msg in details for msg in ["No hostname set", "File is empty", "File format is unknown"]):
                        continue
                    if "No candidates for OSPF router-id" in details:
                        issues.append({"type": "CONFIG_WARNING", "severity": "MEDIUM", "details": details})
                        continue

                    issues.append(
                        {
                            "type": "PARSE_ISSUE",
                            "severity": "HIGH",
                            "details": f"{details} at line: {line_text}",
                        }
                    )

            # Check for Undefined References
            undefined = self.session.q.undefinedReferences().answer().frame()
            if not undefined.empty:
                for _, row in undefined.iterrows():
                    struct_type = row.get('Structure_Type', 'Unknown')
                    struct_name = row.get('Structure_Name', 'Unknown')
                    issues.append(
                        {
                            "type": "UNDEFINED_REFERENCE",
                            "severity": "HIGH",
                            "details": f"File {row.get('File_Name', 'unknown')}: {struct_type} '{struct_name}' is referenced but not defined.",
                        }
                    )

            status = "PASS" if not issues else "FAIL"
            
            # Implementation of Fail-Safe Policy from PAPER.md:
            # "the system defaults to a 'REJECT_FOR_MANUAL_REVIEW' status for any command not supported by the Batfish parser."
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
            return {"status": "ERROR", "error": str(e)}
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    # POC Test
    validator = BatfishValidator()
    # Sample invalid config for testing
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
