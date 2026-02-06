#!/bin/bash
# RAG-NetTwin GNS3 WSL2 Setup Script
# Run this inside your Ubuntu 24.04 terminal

echo "=== GNS3 Server WSL2 Installation ==="

# 1. Add GNS3 PPA
echo "Adding GNS3 PPA..."
sudo add-apt-repository ppa:gns3/ppa -y
sudo apt update

# 2. Install GNS3 Server and QEMU Dependencies
echo "Installing GNS3 Server and QEMU..."
sudo apt install -y gns3-server ubridge qemu-kvm qemu-utils qemu-system-x86 libvirt-clients libvirt-daemon-system virtinst bridge-utils

# 3. Fix Permissions
# ubridge needs to run as root to manage virtual interfaces
echo "Configuring permissions..."
sudo usermod -aG kvm,libvirt,ubridge,docker $USER
sudo chmod u+s /usr/bin/ubridge

# 4. Check for KVM Support
echo "Checking for Nested Virtualization (KVM)..."
sudo apt install -y cpu-checker
kvm-ok

echo ""
echo "=== GNS3 Setup Complete! ==="
echo "Instructions to connect:"
echo "1. Run the server in this terminal: gns3server"
echo "2. On Windows, open the GNS3 GUI."
echo "3. Go to Edit -> Preferences -> Server."
echo "4. Uncheck 'Enable local server'."
echo "5. In 'Remote Servers', add Host: 127.0.0.1, Port: 3080."
echo ""
echo "NOTE: If kvm-ok failed, ensure you have enabled Nested Virtualization in Windows."
echo "PowerShell (Admin): Set-VMProcessor -VMName <Your_WSL_VM_Name> -ExposeVirtualizationExtensions \$true"
