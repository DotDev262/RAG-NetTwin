#!/bin/bash

set -e # Exit immediately if a command exits with a non-zero status

# --- Configuration ---
BASH_SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(dirname "$BASH_SCRIPTS_DIR")"
BATFISH_SETUP_SCRIPT="$BASH_SCRIPTS_DIR/setup_batfish_allinone.sh"
BATFISH_HOST="localhost"
BATFISH_API_PORT="8888" # API port for batfish/allinone image

# --- Functions ---
log_info() {
  echo "INFO: $1"
}

log_success() {
  echo "SUCCESS: $1"
}

log_error() {
  echo "ERROR: $1"
  exit 1
}

# --- Main Script ---

log_info "Starting Batfish setup, verification, and testing..."

# 1. Run Batfish Setup Script
log_info "Running Batfish container setup script..."
if ! bash "$BATFISH_SETUP_SCRIPT"; then
  log_error "Batfish container setup failed. Please check the output above."
fi
log_success "Batfish container setup initiated. Waiting for initialization..."

# The setup script already waits for 60 seconds and tests connection to 8888.
# We'll rely on that for initial connectivity.

# Set environment variables for Python scripts
export BATFISH_HOST="$BATFISH_HOST"
export BATFISH_PORT="$BATFISH_API_PORT"

log_info "BATFISH_HOST set to $BATFISH_HOST"
log_info "BATFISH_PORT set to $BATFISH_API_PORT"

# 2. Verify Batfish Connectivity using Python
log_info "Verifying Batfish connectivity using Python..."
PYTHON_CONNECT_SCRIPT=$(cat <<EOF
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path("$PROJECT_ROOT")))

from src.validation.batfish_validator import BatfishValidator
from src.config import settings
import os

print(f"Python script connecting to Batfish at {os.getenv('BATFISH_HOST')}:{os.getenv('BATFISH_PORT')}")
validator = BatfishValidator()
if validator.session:
    print("Batfish connection successful from Python.")
    sys.exit(0)
else:
    print("Batfish connection FAILED from Python. Check Batfish container status and logs.")
    sys.exit(1)
EOF
)

if ! python -c "$PYTHON_CONNECT_SCRIPT"; then
  log_error "Batfish connectivity verification FAILED."
fi
log_success "Batfish connectivity verified."

# 3. Test Batfish Functionality with a Sample Config
log_info "Testing Batfish functionality with a sample configuration..."
PYTHON_TEST_SCRIPT=$(cat <<EOF
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path("$PROJECT_ROOT")))

from src.validation.batfish_validator import BatfishValidator
from src.config import settings
import os

print(f"Python script testing Batfish functionality at {os.getenv('BATFISH_HOST')}:{os.getenv('BATFISH_PORT')}")
validator = BatfishValidator()
if not validator.session:
    print("Batfish session not established, cannot run functionality test.")
    sys.exit(1)

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

try:
    result = validator.validate(test_configs)
    print("
--- Batfish Validation Result ---")
    print(json.dumps(result, indent=2))
    if result.get("status") == "PASS" or result.get("status") == "WARNING":
        print("Batfish functionality test: PASSED (or with WARNINGS).")
        sys.exit(0)
    else:
        print("Batfish functionality test: FAILED.")
        sys.exit(1)
except Exception as e:
    print(f"An error occurred during Batfish functionality test: {e}")
    sys.exit(1)
EOF
)

if ! python -c "$PYTHON_TEST_SCRIPT"; then
  log_error "Batfish functionality test FAILED."
fi
log_success "Batfish functionality test PASSED."

log_success "Batfish setup, verification, and testing completed successfully!"
