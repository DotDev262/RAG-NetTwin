import os
import socket
import struct

# Get the hostid of the system
hostid = os.popen("hostid").read().strip()
try:
    hostid = int(hostid, 16)
except ValueError:
    print(f"Error: Could not parse hostid '{hostid}'")
    exit(1)

hostname = socket.gethostname()
print(f"*********************************************************************")
print(f"Cisco IOL License Generator (Python 3)")
print(f"Hostname: {hostname}")
print(f"Hostid:   {hostid:08x}")

# The classic IOU/IOL license generation logic
# This is a standard research utility for the GNS3 community
ioukey = int(hostid)
iouPad1 = b'\x4B\x58\x21\xAD'
iouPad2 = b'\x4B\x58\x21\xAD'

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
import hashlib
m = hashlib.md5()
m.update(struct.pack('I', ioukey))
m.update(hostname.encode('utf-8'))
final_key = m.hexdigest()[:16]

print(f"*********************************************************************")
print(f"\nYour iourc file content should be:\n")
print(f"[license]")
print(f"{hostname} = {final_key};")
print(f"\n*********************************************************************")

# Also write it to a file directly for convenience
with open("iourc", "w") as f:
    f.write("[license]\n")
    f.write(f"{hostname} = {final_key};\n")

print(f"File 'iourc' has been created in the current directory.")
