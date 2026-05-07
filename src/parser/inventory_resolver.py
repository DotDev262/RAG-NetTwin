"""
Inventory Resolver Module for RAG-NetTwin.

This module resolves device metadata (vendor, OS type, version) from
an inventory source. It supports both local JSON inventory files
and live device queries via NAPALM for real-time metadata retrieval.

Key Features:
- Local JSON inventory file support
- NAPALM integration for live device queries
- Smart fallback defaults when device not found
- Priority-based resolution (live > local > defaults)

Typical Usage:
    from src.parser.inventory_resolver import InventoryResolver

    resolver = InventoryResolver()
    metadata = resolver.resolve("Router-A")
    print(metadata)  # {'name': 'Router-A', 'vendor': 'cisco', 'os_type': 'ios-xe', 'os_version': '17.6', 'found_in_inventory': True}
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


class InventoryResolver:
    """
    Resolves device metadata (vendor, OS, version) from an inventory.

    This class provides a unified interface for resolving device information
    needed for version-locked RAG retrieval. It supports three resolution
    methods with the following priority:

    1. Local Inventory: JSON file mapping hostnames to metadata
    2. Live Query (NAPALM): Query device directly for facts
    3. Defaults: Cisco IOS-XE 17.6 (safe fallback)

    The resolver adds a 'found_in_inventory' key to indicate whether
    the device was actually found in the inventory or if defaults
    were used.

    Attributes:
        inventory_path: Path to the local inventory JSON file.
            Can be overridden via INVENTORY_PATH environment variable.
        inventory: Loaded inventory data as a dictionary.

    Example:
        # With inventory.json containing:
        # {"Router-A": {"vendor": "cisco", "os_type": "ios-xe", "os_version": "17.6"}}
        >>> resolver = InventoryResolver()
        >>> metadata = resolver.resolve("Router-A")
        >>> metadata['found_in_inventory']
        True
    """

    def __init__(self, inventory_path: Optional[str] = None):
        """
        Initialize the InventoryResolver.

        Args:
            inventory_path: Optional path to inventory JSON file.
                Defaults to INVENTORY_PATH env var or "data/inventory.json".
        """
        self.inventory_path: str = (
            inventory_path
            or os.getenv("INVENTORY_PATH", "data/inventory.json")
            or "data/inventory.json"
        )
        self.inventory = self._load_inventory()

    def _load_inventory(self) -> Dict[str, Any]:
        """
        Load local inventory mapping from JSON file.

        Returns:
            Dictionary mapping hostname to device metadata.
            Empty dictionary if file not found or invalid.

        Note:
            Silently handles errors - returns empty dict if file
            doesn't exist or is malformed. This allows the system
            to fall back to defaults gracefully.
        """
        path = Path(self.inventory_path)
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load inventory from {path}: {e}")
        return {}

    def resolve(self, hostname: str) -> Dict[str, Any]:
        """
        Main entry point to resolve device facts.

        This method attempts to resolve device metadata using the
        configured resolution methods in priority order. It always
        adds a 'found_in_inventory' key to indicate the resolution source.

        Args:
            hostname: Device hostname to resolve (e.g., "Router-A").

        Returns:
            Dictionary containing:
                - name: Device hostname
                - vendor: Device vendor (e.g., "cisco", "juniper")
                - os_type: OS type (e.g., "ios-xe", "junos")
                - os_version: OS version (e.g., "17.6", "21.4")
                - found_in_inventory: Boolean indicating if device
                  was found in inventory (vs. using defaults)

        Note:
            The returned dictionary always has all required keys,
            even if the device wasn't found. Use 'found_in_inventory'
            to determine confidence in the data.

        Example:
            >>> resolver = InventoryResolver()
            >>> result = resolve("CORE-SW-01")
            >>> if result['found_in_inventory']:
            ...     print(f"Using inventory data: {result['os_version']}")
            ... else:
            ...     print("Using defaults")
        """
        # Priority 1: Try Local Inventory
        # Check if hostname exists in local JSON inventory
        if hostname in self.inventory:
            result = self.inventory[hostname].copy()
            result["found_in_inventory"] = True
            return result

        # Priority 2: Try NAPALM (Live Query)
        # Only attempt if credentials are available in environment
        if os.getenv("NAPALM_USERNAME"):
            try:
                result = self._query_live_device(hostname)
                result["found_in_inventory"] = True
                return result
            except Exception as e:
                print(f"Warning: Live query failed for {hostname}: {e}")

        # Priority 3: Fallback to reasonable defaults
        # Cisco IOS-XE 17.6 is the most tested version
        return {
            "name": hostname,
            "vendor": "cisco",
            "os_type": "ios-xe",
            "os_version": "17.6",
            "found_in_inventory": False,
        }

    def _query_live_device(self, hostname: str) -> Dict[str, str]:
        """
        Uses NAPALM to fetch real version info from a device.

        This method connects to a live network device and retrieves
        its facts (vendor, OS version, model, etc.). It handles the
        connection lifecycle and automatically selects the appropriate
        NAPALM driver based on the hostname.

        Args:
            hostname: Device hostname or IP address to query.

        Returns:
            Dictionary with device metadata:
                - name: Device hostname
                - vendor: Lowercase vendor name
                - os_type: "junos" for Juniper, "ios-xe" for Cisco
                - os_version: OS version string from device

        Raises:
            Exception: If NAPALM connection fails. Caller should handle
                gracefully as this is optional functionality.

        Note:
            Requires NAPALM_USERNAME and NAPALM_PASSWORD environment variables.
            Optionally NAPALM_PORT can be set (default 22).
        """
        import napalm

        # Determine driver from hostname suffix or default to 'ios'
        # .j suffix typically indicates Juniper
        driver_name = "ios"
        if "juniper" in hostname.lower() or hostname.endswith(".j"):
            driver_name = "junos"

        # Create NAPALM driver instance
        driver = napalm.get_network_driver(driver_name)
        device = driver(
            hostname=hostname,
            username=os.getenv("NAPALM_USERNAME"),
            password=os.getenv("NAPALM_PASSWORD"),
            optional_args={"port": os.getenv("NAPALM_PORT", 22)},
        )

        # Connect and get facts
        with device:
            facts = device.get_facts()
            return {
                "name": hostname,
                "vendor": facts.get("vendor", "cisco").lower(),
                "os_type": driver_name if driver_name == "junos" else "ios-xe",
                "os_version": facts.get("os_version", "17.6"),
            }


if __name__ == "__main__":
    # POC Test - demonstrates usage
    resolver = InventoryResolver()

    # Add mock data if file missing (for testing)
    resolver.inventory["CORE-SW-01"] = {
        "vendor": "cisco",
        "os_type": "ios-xe",
        "os_version": "17.3",
    }

    print(f"Resolving known: {resolver.resolve('CORE-SW-01')}")
    print(f"Resolving unknown: {resolver.resolve('RANDOM-RTR')}")
