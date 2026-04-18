import requests
import json
import sys
from pathlib import Path

# Add src to path for settings
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from config import settings

def test_gns3():
    host = "127.0.0.1" # Explicitly use IP
    port = settings.gns3_port
    base_url = f"http://{host}:{port}/v2"
    auth = ("admin", "gns3") # Default GNS3 credentials
    
    print(f"--- GNS3 Connectivity Test ---")
    print(f"Target: {base_url}")
    
    try:
        # 1. Test Version
        print(f"\n1. Checking Server Version...")
        resp = requests.get(f"{base_url}/version", timeout=5, auth=auth)
        if resp.status_code == 200:
            version = resp.json().get('version')
            print(f"   ✅ SUCCESS: Connected to GNS3 Server v{version}")
        else:
            print(f"   ❌ FAILED: Status code {resp.status_code}")
            return

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
        print(f"\n3. Checking for Cisco IOL/IOU Templates...")
        resp = requests.get(f"{base_url}/templates", timeout=5, auth=auth)

        if resp.status_code == 200:
            templates = resp.json()
            iou_templates = [t for t in templates if t.get('type') == 'iou']
            if iou_templates:
                print(f"   ✅ SUCCESS: Found {len(iou_templates)} IOU templates ready for Twin.")
                for t in iou_templates:
                    print(f"      - {t.get('name')}")
            else:
                print(f"   ⚠️  WARNING: No IOU templates found. Ensure you added the IOL image in GNS3.")
        
        print(f"\n--- Test Complete ---")
        print(f"Your environment is ready for the Digital Twin verification!")

    except requests.exceptions.ConnectionError:
        print(f"   ❌ FAILED: Connection Refused. Ensure GNS3 is open and running.")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")

if __name__ == "__main__":
    test_gns3()
