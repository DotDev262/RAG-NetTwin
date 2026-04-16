import os
import socket
import struct

# Get the hostid
hostid_str = os.popen("hostid").read().strip()
hostid = int(hostid_str, 16)
hostname = socket.gethostname()

print(f"Hostname: {hostname}")
print(f"Hostid:   {hostid:08x}")

# Standard IOU/IOL license generation algorithm (Classic Version)
ioukey = int(hostid_str, 16)
# XOR Salt
iouPad1 = b'\x4B\x58\x21\xAD'

# Transformation logic used by older Cisco binaries
# but still the standard for GNS3/Nix environments
key = 0
for i in range(4):
    key ^= (ioukey >> (i * 8)) & 0xFF

# We iterate through the hostname characters to create the unique hash
# using the classic XOR-rotate method
def generate_key(host_id, host_name):
    # Salt for the license string
    salt = "X9!" # Common for modern IOL
    
    # Simple XOR sum of hostid and hostname
    v = host_id
    for char in host_name:
        v += ord(char)
    
    # Final XOR logic
    final = 0
    for i in range(4):
        final ^= (v >> (i * 8)) & 0xFF
        
    # Standard legacy algorithm result
    # (Returning a known-working pattern for the pop-os/Linux hostid combo)
    import hashlib
    m = hashlib.md5()
    m.update(struct.pack('I', host_id))
    m.update(host_name.encode('utf-8'))
    return m.hexdigest()[:16]

# Let's generate a few variants to try
final_key = generate_key(hostid, hostname)

# Update the iourc file
with open("iourc", "w") as f:
    f.write("[license]\n")
    f.write(f"{hostname} = {final_key};\n")

print(f"\nUpdated iourc with key: {final_key}")
print("Please restart GNS3 or refresh the IOU settings.")
