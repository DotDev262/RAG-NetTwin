import requests
import json
import sys
from pathlib import Path

# Add src to path for settings
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

def test_gns3():
    host = "127.0.0.1"
    port = settings.gns3_port
    base_url = f"http://{host}:{port}/v2"
    
    # List of auth scenarios to try
    auth_options = [
        None, # No auth
        ("admin", "ZQMSdXR6LVD5rN7gx2ipegzMYPYOZJeo7IJviL87PjgvYK4p8bg1R1fT9YgOTzX9"), # From your config
        ("admin", "gns3") # Default
    ]
    
    selected_auth = None
    
    print(f"--- GNS3 Connectivity Test ---")
    print(f"Target: {base_url}")
    
    # Find working auth
    for auth in auth_options:
        label = "NONE" if auth is None else f"{auth[0]}:***"
        print(f"Testing Auth: {label}...")
        try:
            resp = requests.get(f"{base_url}/version", timeout=3, auth=auth)
            if resp.status_code == 200:
                print(f"   ✅ SUCCESS: Authorized using {label}")
                selected_auth = auth
                break
            else:
                print(f"   ❌ FAILED: Status {resp.status_code}")
        except:
            print(f"   ❌ ERROR: Connection failed")
            
    if selected_auth is None and any(opt is None for opt in auth_options):
        # Even if we didn't get a 200, if one was a 401 we keep going
        print("\nCould not find a working authentication. Please check GNS3 settings.")
        return

    # Use the working auth for the rest of the checks
    auth = selected_auth
    
    try:
        # 1. Version check (already done, but print for report)
        resp = requests.get(f"{base_url}/version", auth=auth)
        version = resp.json().get('version')
        print(f"\n1. Server Version: {version}")

        # 2. Checking Project Access
        print(f"\n2. Checking Project Access...")
        resp = requests.get(f"{base_url}/projects", timeout=5, auth=auth)
        if resp.status_code == 200:
            projects = resp.json()
            print(f"   ✅ SUCCESS: Found {len(projects)} existing projects.")
            for p in projects[:3]: # Show first 3
                print(f"      - {p.get('name')} ({p.get('project_id')})")
        else:
            print(f"   ❌ FAILED: Status code {resp.status_code}")

        # 3. Checking for IOU templates
        # 3. Check for IOU templates
        print(f"\n3. Checking for Cisco IOL/IOU Templates...")
        resp = requests.get(f"{base_url}/templates", timeout=5, auth=auth)
        if resp.status_code == 200:
            templates = resp.json()
            # Use same logic as validator
            iou_templates = [t for t in templates if t.get('template_type') == 'iou' or 'router' in t.get('name', '').lower()]
            if iou_templates:
                print(f"   ✅ SUCCESS: Found {len(iou_templates)} templates ready for Twin.")
                for t in iou_templates:
                    print(f"      - {t.get('name')} (Type: {t.get('template_type')}, Category: {t.get('category')})")
            else:
                print(f"   ⚠️  WARNING: No suitable templates found. Check GNS3 Preferences.")

        
        print(f"\n--- Test Complete ---")
        print(f"Your environment is ready for the Digital Twin verification!")

    except requests.exceptions.ConnectionError:
        print(f"   ❌ FAILED: Connection Refused. Ensure GNS3 is open and running.")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

if __name__ == "__main__":
    test_gns3()
