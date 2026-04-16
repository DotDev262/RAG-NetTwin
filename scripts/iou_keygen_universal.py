import os
import socket
import hashlib
import struct

def generate_iou_key(hostid_str, hostname):
    ioukey = int(hostid_str, 16)
    for char in hostname:
        ioukey += ord(char)
    
    iouPad1 = b'\x4B\x58\x21\xAD'
    iouPad2 = b'\x4B\x58\x21\xAD'
    
    # Try both Little-Endian and Big-Endian as different binaries prefer different ones
    md5_le = hashlib.md5(iouPad1 + iouPad2 + struct.pack('<I', ioukey) + hostname.encode('utf-8')).hexdigest()[:16]
    md5_be = hashlib.md5(iouPad1 + iouPad2 + struct.pack('!I', ioukey) + hostname.encode('utf-8')).hexdigest()[:16]
    
    return md5_le, md5_be

hostname = socket.gethostname()
sys_hostid = os.popen("hostid").read().strip()

# Generate keys for System HostID
le1, be1 = generate_iou_key(sys_hostid, hostname)
# Generate keys for Zero HostID (Common Linux fix)
le2, be2 = generate_iou_key("00000000", hostname)

print(f"Generating Universal iourc for {hostname}...")

with open("iourc", "w") as f:
    f.write("[license]\n")
    # We can't have multiple keys for the same hostname in one file, 
    # but we will print them so you can try them.
    f.write(f"{hostname} = {le1};\n")

print(f"\n--- TRY THESE KEYS IN ORDER ---")
print(f"1. System (LE): {le1}  <-- Currently in your iourc")
print(f"2. System (BE): {be1}")
print(f"3. Zero ID (LE): {le2}")
print(f"4. Zero ID (BE): {be2}")
print(f"--------------------------------")
print("\nIf the first one fails, manually edit the 'iourc' file and replace the key with the next one in the list.")
