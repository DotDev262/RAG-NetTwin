#!/bin/bash
# RAG-NetTwin WSL2 Setup Script
# Run this inside your Ubuntu 24.04 terminal

echo "=== RAG-NetTwin WSL2 Environment Setup ==="

# 1. Update System
sudo apt update && sudo apt upgrade -y

# 2. Install Docker (Required for Batfish & Containerlab)
echo "Installing Docker..."
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo 
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu 
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | 
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
echo "✓ Docker installed (You may need to restart your terminal later for group changes)"

# 3. Install Containerlab (Tier 2)
echo "Installing Containerlab..."
bash -c "$(curl -sL https://get.containerlab.dev)"
echo "✓ Containerlab installed"

# 4. Start Batfish (Tier 1)
echo "Starting Batfish Container..."
docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
echo "✓ Batfish is running"

# 5. Setup Python Environment
echo "Setting up Python..."
sudo apt install -y python3-venv python3-pip
# Install 'uv' for faster management
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

echo "=== Setup Complete! ==="
echo "Next steps:"
echo "1. Restart your WSL terminal."
echo "2. Navigate to this project directory: cd /mnt/c/Users/Aryan/Documents/Projects/RAG-NetTwin"
echo "3. Run the evaluation: uv run python src/evaluation/evaluator.py"
