import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from config import settings


class InventoryResolver:
    """
    Resolves device metadata (vendor, OS, version) from an inventory.
    Can use a local JSON file (mock) or live device queries via NAPALM.
    """

    def __init__(self, inventory_path: Optional[str] = None):
        self.inventory_path = inventory_path or os.getenv(
            "INVENTORY_PATH", "data/inventory.json"
        )
        self.inventory = self._load_inventory()

    def _load_inventory(self) -> Dict[str, Any]:
        """Load local inventory mapping hostname -> metadata"""
        path = Path(self.inventory_path)
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load inventory from {path}: {e}")
        return {}

    def resolve(self, hostname: str) -> Dict[str, str]:
        """
        Main entry point to resolve device facts.
        Priority: 1. Live Query (if enabled), 2. Local Inventory, 3. Defaults.
        Returns dict with 'found' key indicating if hostname was in inventory.
        """
        # 1. Try Local Inventory
        if hostname in self.inventory:
            result = self.inventory[hostname].copy()
            result["found_in_inventory"] = True
            return result

        # 2. Try NAPALM (Live Query) if credentials exist in ENV
        if os.getenv("NAPALM_USERNAME"):
            try:
                result = self._query_live_device(hostname)
                result["found_in_inventory"] = True
                return result
            except Exception as e:
                print(f"Warning: Live query failed for {hostname}: {e}")

        # 3. Fallback to reasonable defaults (Cisco 17.6) - NOT found
        return {
            "name": hostname,
            "vendor": "cisco",
            "os_type": "ios-xe",
            "os_version": "17.6",
            "found_in_inventory": False,
        }

    def _query_live_device(self, hostname: str) -> Dict[str, str]:
        """Uses NAPALM to fetch real version info from a device."""
        import napalm

        # Determine driver from hostname suffix or default to 'ios'
        driver_name = "ios"
        if "juniper" in hostname.lower() or hostname.endswith(".j"):
            driver_name = "junos"

        driver = napalm.get_network_driver(driver_name)
        device = driver(
            hostname=hostname,
            username=os.getenv("NAPALM_USERNAME"),
            password=os.getenv("NAPALM_PASSWORD"),
            optional_args={"port": os.getenv("NAPALM_PORT", 22)},
        )

        with device:
            facts = device.get_facts()
            return {
                "name": hostname,
                "vendor": facts.get("vendor", "cisco").lower(),
                "os_type": driver_name if driver_name == "junos" else "ios-xe",
                "os_version": facts.get("os_version", "17.6"),
            }


if __name__ == "__main__":
    # POC Test
    resolver = InventoryResolver()
    # Mock data if file missing
    resolver.inventory["CORE-SW-01"] = {
        "vendor": "cisco",
        "os_type": "ios-xe",
        "os_version": "17.3",
    }

    print(f"Resolving known: {resolver.resolve('CORE-SW-01')}")
    print(f"Resolving unknown: {resolver.resolve('RANDOM-RTR')}")
