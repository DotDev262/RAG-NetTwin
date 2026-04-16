import os
import socket
import hashlib
import struct

# Get hostid and hostname
hostid_str = os.popen("hostid").read().strip()
hostid = int(hostid_str, 16)
hostname = socket.gethostname()

# The "Classic" IOU/IOL Algorithm
# This specific combination of pads and packing is what most IOL binaries expect
ioukey = hostid
for char in hostname:
    ioukey += ord(char)

# Common salt/padding used in Cisco IOL internal license checks
iouPad1 = b'\x4B\x58\x21\xAD'
iouPad2 = b'\x4B\x58\x21\xAD'

# Create the MD5 hash of the padded data
# Note the Big-Endian ('!I') packing of the calculated ioukey
md5input = iouPad1 + iouPad2 + struct.pack('!I', ioukey) + hostname.encode('utf-8')
license_key = hashlib.md5(md5input).hexdigest()[:16]

print(f"*********************************************************************")
print(f"Classic Cisco IOL License Generator")
print(f"Hostname: {hostname}")
print(f"Hostid:   {hostid:08x}")
print(f"Key:      {license_key}")
print(f"*********************************************************************")

with open("iourc", "w") as f:
    f.write("[license]\n")
    f.write(f"{hostname} = {license_key};\n")

print(f"\nCreated 'iourc' with key: {license_key}")
