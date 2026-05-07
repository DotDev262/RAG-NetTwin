#!/usr/bin/env python3
"""
GNS3 Project Cleanup Utility.
Deletes all projects from the GNS3 server to ensure a clean state.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import requests

# Add src to path for settings
from src.config import settings  # noqa: E402


def clear_all_projects():
    host = settings.gns3_host if settings.gns3_host != "localhost" else "127.0.0.1"
    port = settings.gns3_port
    base_url = f"http://{host}:{port}/v2"

    # Credentials from gns3_validator.py
    auth = ("admin", "ZQMSdXR6LVD5rN7gx2ipegzMYPYOZJeo7IJviL87PjgvYK4p8bg1R1fT9YgOTzX9")

    print(f"Connecting to GNS3 at {base_url}...")

    try:
        # Get list of all projects
        resp = requests.get(f"{base_url}/projects", auth=auth)
        if resp.status_code != 200:
            print(f"Failed to fetch projects: {resp.status_code} {resp.text}")
            return

        projects = resp.json()
        if not projects:
            print("No projects found.")
            return

        print(f"Found {len(projects)} projects. Deleting...")

        for project in projects:
            name = project.get("name", "Unknown")
            pid = project.get("project_id")

            # Close first if opened
            if project.get("status") == "opened":
                requests.post(f"{base_url}/projects/{pid}/close", auth=auth)

            # Delete project
            del_resp = requests.delete(f"{base_url}/projects/{pid}", auth=auth)
            if del_resp.status_code in [200, 204]:
                print(f"  ✓ Deleted project: {name} ({pid})")
            else:
                print(f"  ✗ Failed to delete {name}: {del_resp.status_code}")

        print("\nCleanup complete.")

    except Exception as e:
        print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    confirm = input("This will delete ALL GNS3 projects. Are you sure? (y/N): ")
    if confirm.lower() == "y":
        clear_all_projects()
    else:
        print("Aborted.")
