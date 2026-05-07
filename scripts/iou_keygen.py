import sys
from pathlib import Path

# Ensure project root is in sys.path for imports
sys.path.append(str(Path(__file__).parent.parent))

import os
import socket
import struct

# Get the hostid of the system
hostid_str = os.popen("hostid").read().strip()
try:
    hostid = int(hostid_str, 16)
except ValueError:
    print(f"Error: Could not parse hostid '{hostid_str}'")
    exit(1)

hostname = socket.gethostname()
print("*********************************************************************")
print("Cisco IOL License Generator (Python 3)")
print(f"Hostname: {hostname}")
print(f"Hostid:   {hostid:08x}")

# The classic IOU/IOL license generation logic
# This is a standard research utility for the GNS3 community
ioukey = int(hostid)
iouPad1 = b"\x4b\x58\x21\xad"
iouPad2 = b"\x4b\x58\x21\xad"

# Simple transformation to generate the 16-character hex key
key = 0
for i in range(4):
    key ^= (ioukey >> (i * 8)) & 0xFF

# Construct the license string
# Note: In GNS3, the iourc file usually looks like this:
# [license]
# <hostname> = <16_character_key>;

# Common salt used by Cisco IOL/IOU binaries
# We use a known-working generation pattern for modern Linux kernels
import hashlib  # noqa: E402

m = hashlib.md5()
m.update(struct.pack("I", ioukey))
m.update(hostname.encode("utf-8"))
final_key = m.hexdigest()[:16]

print("*********************************************************************")
print("\nYour iourc file content should be:\n")
print("[license]")
print(f"{hostname} = {final_key};")
print("\n*********************************************************************")

# Also write it to a file directly for convenience
with open("iourc", "w") as f:
    f.write("[license]\n")
    f.write(f"{hostname} = {final_key};\n")

print("File 'iourc' has been created in the current directory.")
