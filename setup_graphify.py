import os
import subprocess
import json
from pathlib import Path


def resolve_python():
    # Try uv
    try:
        result = subprocess.run(
            [
                "uv",
                "tool",
                "run",
                "graphifyy",
                "python",
                "-c",
                "import sys; print(sys.executable)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    # Try which
    try:
        graphify_bin = subprocess.run(
            ["which", "graphify"], capture_output=True, text=True
        ).stdout.strip()
        if graphify_bin:
            with open(graphify_bin, "r") as f:
                shebang = f.readline().strip()
                if shebang.startswith("#!"):
                    return shebang[2:]
    except Exception:
        pass

    return "python3"


python_path = resolve_python()
print(f"Using python: {python_path}")

# Ensure graphify-out exists
os.makedirs("graphify-out", exist_ok=True)

with open("graphify-out/.graphify_python", "w") as f:
    f.write(python_path)

with open("graphify-out/.graphify_root", "w") as f:
    f.write(os.getcwd())

# Import graphify and run detect
try:
    # We might need to use the resolved python to run the detection if the current one doesn't have it
    # But let's try current first if it's the same or has it
    from graphify.detect import detect  # type: ignore

    result = detect(Path("."))
    with open("graphify-out/.graphify_detect.json", "w") as f:
        json.dump(result, f)
    print("Detection successful")
except ImportError:
    print("Graphify not found in current environment, trying resolved python")
    subprocess.run(
        [
            python_path,
            "-c",
            """
import json
from graphify.detect import detect
from pathlib import Path
result = detect(Path('.'))
with open('graphify-out/.graphify_detect.json', 'w') as f:
    json.dump(result, f)
""",
        ],
        check=True,
    )
    print("Detection successful via resolved python")
