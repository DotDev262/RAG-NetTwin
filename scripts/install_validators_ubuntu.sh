#!/bin/bash
# RAG-NetTwin Three-Tier Validator Installation Script for Ubuntu
# Supports both Docker and Podman container runtimes
# Usage: sudo ./install_validators_ubuntu.sh [OPTIONS]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUNTIME=""
TIERS="all"
VERIFY_MODE=false
DRY_RUN=false
UNINSTALL_MODE=false

# Detect package manager (nala preferred over apt)
detect_pkg_manager() {
    if command -v nala &> /dev/null; then
        echo "nala"
    else
        echo "apt-get"
    fi
}

PKG_MANAGER=$(detect_pkg_manager)

# Package manager wrapper functions
pkg_update() {
    if [[ "$PKG_MANAGER" == "nala" ]]; then
        nala update
    else
        apt-get update
    fi
}

pkg_install() {
    if [[ "$PKG_MANAGER" == "nala" ]]; then
        nala install -y "$@"
    else
        apt-get install -y "$@"
    fi
}

pkg_remove() {
    if [[ "$PKG_MANAGER" == "nala" ]]; then
        nala remove -y "$@"
    else
        apt-get remove -y "$@"
    fi
}

pkg_purge() {
    if [[ "$PKG_MANAGER" == "nala" ]]; then
        nala purge -y "$@"
    else
        apt-get purge -y "$@"
    fi
}

pkg_autoremove() {
    if [[ "$PKG_MANAGER" == "nala" ]]; then
        nala autoremove -y
    else
        apt-get autoremove -y
    fi
}

# Print functions
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Help message
show_help() {
    cat << EOF
RAG-NetTwin Three-Tier Validator Installation Script

Usage: sudo ./install_validators_ubuntu.sh [OPTIONS]

Options:
    --runtime=docker      Use Docker (default)
    --runtime=podman      Use Podman
    --tier1               Install only Batfish (Tier 1)
    --tier2               Install only Containerlab (Tier 2)
    --tier3               Install only GNS3 (Tier 3)
    --verify              Verify existing installation
    --uninstall           Remove all validators and configuration
    --dry-run             Show what would be installed
    -h, --help            Show this help message

Examples:
    sudo ./install_validators_ubuntu.sh                    # Interactive mode
    sudo ./install_validators_ubuntu.sh --runtime=docker   # Use Docker
    sudo ./install_validators_ubuntu.sh --runtime=podman   # Use Podman
    sudo ./install_validators_ubuntu.sh --tier1 --tier2    # Install Tiers 1 & 2 only
    sudo ./install_validators_ubuntu.sh --verify           # Check installation
    sudo ./install_validators_ubuntu.sh --uninstall        # Remove everything

Package Manager: ${PKG_MANAGER}

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --runtime=docker)
                RUNTIME="docker"
                shift
                ;;
            --runtime=podman)
                RUNTIME="podman"
                shift
                ;;
            --tier1)
                TIERS="1"
                shift
                ;;
            --tier2)
                TIERS="2"
                shift
                ;;
            --tier3)
                TIERS="3"
                shift
                ;;
            --verify)
                VERIFY_MODE=true
                shift
                ;;
            --uninstall)
                UNINSTALL_MODE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect existing container runtime
detect_runtime() {
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null 2>&1; then
            print_info "Docker detected and running"
            RUNTIME="docker"
            return 0
        fi
    fi
    
    if command -v podman &> /dev/null; then
        if podman info &> /dev/null 2>&1; then
            print_info "Podman detected and running"
            RUNTIME="podman"
            return 0
        fi
    fi
    
    return 1
}

# Prompt user for runtime choice
prompt_runtime_choice() {
    echo ""
    print_header "Container Runtime Selection"
    echo "No container runtime detected. Which would you like to install?"
    echo ""
    echo "1) Docker (Recommended)"
    echo "   - Better compatibility with Batfish and Containerlab"
    echo "   - Extensive documentation and community support"
    echo "   - Easier troubleshooting"
    echo ""
    echo "2) Podman"
    echo "   - More secure, daemonless architecture"
    echo "   - Better for production environments"
    echo "   - Requires additional configuration"
    echo ""
    
    read -p "Enter choice [1-2] (default: 1): " choice
    
    # Default to Docker if no input
    if [[ -z "$choice" ]]; then
        choice="1"
    fi
    
    case $choice in
        1)
            RUNTIME="docker"
            ;;
        2)
            RUNTIME="podman"
            ;;
        *)
            print_warning "Invalid choice. Defaulting to Docker."
            RUNTIME="docker"
            ;;
    esac
    
    echo ""
}

# Show installation summary and confirm
confirm_installation() {
    echo ""
    print_header "Installation Summary"
    echo "Runtime: $RUNTIME (Rootful)"
    echo "Package Manager: $PKG_MANAGER"
    echo ""
    
    if [[ "$TIERS" == "all" ]]; then
        echo "Tier 1 (Batfish - Static Analysis): Will be installed"
        echo "Tier 2 (Containerlab - Emulation): Will be installed"
        echo "Tier 3 (GNS3 - Simulation): Will be installed"
    else
        [[ "$TIERS" == *"1"* ]] && echo "Tier 1 (Batfish): Will be installed"
        [[ "$TIERS" == *"2"* ]] && echo "Tier 2 (Containerlab): Will be installed"
        [[ "$TIERS" == *"3"* ]] && echo "Tier 3 (GNS3): Will be installed"
    fi
    
    echo ""
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "DRY RUN MODE - No changes will be made"
        return 0
    fi
    
    read -p "Proceed with installation? [Y/n]: " confirm
    
    if [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]]; then
        return 0
    else
        print_info "Installation cancelled by user"
        exit 0
    fi
}

# Show uninstallation summary and confirm
confirm_uninstallation() {
    echo ""
    print_header "Uninstallation Summary"
    echo "This will REMOVE the following:"
    echo ""
    
    if [[ "$TIERS" == "all" ]]; then
        echo "- Batfish container and systemd service"
        echo "- Containerlab binary"
        echo "- GNS3 server, ubridge, and configuration"
        echo "- Docker/Podman containers and images"
        echo "- All configuration files"
    else
        [[ "$TIERS" == *"1"* ]] && echo "- Batfish container and service"
        [[ "$TIERS" == *"2"* ]] && echo "- Containerlab binary"
        [[ "$TIERS" == *"3"* ]] && echo "- GNS3 server and configuration"
    fi
    
    echo ""
    print_warning "This action cannot be undone!"
    echo ""
    
    if [[ "$DRY_RUN" == true ]]; then
        print_info "DRY RUN MODE - No changes will be made"
        return 0
    fi
    
    read -p "Are you sure you want to uninstall? [y/N]: " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        return 0
    else
        print_info "Uninstallation cancelled"
        exit 0
    fi
}

# Install Docker (Rootful)
install_docker() {
    print_header "Installing Docker Engine"
    
    # Update apt
    pkg_update
    
    # Install prerequisites
    pkg_install \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Update apt and install Docker
    pkg_update
    pkg_install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker service
    systemctl start docker
    systemctl enable docker
    
    # Add current user to docker group
    if [[ -n "$SUDO_USER" ]]; then
        usermod -aG docker "$SUDO_USER"
        print_info "Added user $SUDO_USER to docker group"
        print_warning "You may need to log out and back in for group changes to take effect"
    fi
    
    print_success "Docker installed successfully"
}

# Uninstall Docker
uninstall_docker() {
    print_header "Uninstalling Docker"
    
    # Stop and remove all containers
    if command -v docker &> /dev/null; then
        print_info "Stopping and removing all Docker containers..."
        docker stop $(docker ps -aq) 2>/dev/null || true
        docker rm $(docker ps -aq) 2>/dev/null || true
        docker system prune -af --volumes 2>/dev/null || true
    fi
    
    # Remove Docker packages
    pkg_purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker.io
    
    # Remove Docker repository and GPG key
    rm -f /etc/apt/sources.list.d/docker.list
    rm -f /etc/apt/keyrings/docker.gpg
    
    print_success "Docker uninstalled"
}

# Install Podman (Rootful)
install_podman() {
    print_header "Installing Podman"
    
    # Update apt
    pkg_update
    
    # Install Podman and compatibility tools
    pkg_install podman podman-docker
    
    # Enable Podman socket for Docker compatibility
    systemctl enable podman.socket
    systemctl start podman.socket
    
    # Create Docker compatibility symlink
    if [[ ! -e /var/run/docker.sock ]]; then
        ln -s /run/podman/podman.sock /var/run/docker.sock
    fi
    
    # Configure registries
    if [[ ! -f /etc/containers/registries.conf ]]; then
        mkdir -p /etc/containers
        cat > /etc/containers/registries.conf << EOF
[registries.search]
registries = ['docker.io', 'quay.io', 'registry.fedoraproject.org']
EOF
    fi
    
    print_success "Podman installed successfully"
    print_info "Podman is configured to be Docker-compatible"
}

# Uninstall Podman
uninstall_podman() {
    print_header "Uninstalling Podman"
    
    # Stop and remove all containers
    if command -v podman &> /dev/null; then
        print_info "Stopping and removing all Podman containers..."
        podman stop -a 2>/dev/null || true
        podman rm -a 2>/dev/null || true
        podman system prune -af 2>/dev/null || true
    fi
    
    # Remove Podman packages
    pkg_purge podman podman-docker
    
    # Remove compatibility symlink
    rm -f /var/run/docker.sock
    
    print_success "Podman uninstalled"
}

# Setup Tier 1: Batfish
setup_batfish() {
    print_header "Setting up Tier 1: Batfish (Static Analysis)"
    
    # Pull Batfish image
    print_info "Pulling Batfish image..."
    if [[ "$RUNTIME" == "docker" ]]; then
        docker pull batfish/batfish:latest
    else
        podman pull docker.io/batfish/batfish:latest
    fi
    
    # Create systemd service for Batfish
    cat > /etc/systemd/system/batfish.service << EOF
[Unit]
Description=Batfish Network Configuration Analyzer
After=${RUNTIME}.service
Requires=${RUNTIME}.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStartPre=-/${RUNTIME} rm -f batfish
ExecStart=/${RUNTIME} run \\
    --name batfish \\
    --rm \\
    -p 9996:9996 \\
    -p 9997:9997 \\
    batfish/batfish:latest
ExecStop=-/${RUNTIME} stop batfish
ExecStopPost=-/${RUNTIME} rm -f batfish

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and start Batfish
    systemctl daemon-reload
    systemctl enable batfish
    systemctl start batfish
    
    # Wait for Batfish to be ready
    print_info "Waiting for Batfish to start (this may take 30-60 seconds)..."
    
    # Verify Batfish is running
    local max_attempts=12
    for i in $(seq 1 $max_attempts); do
        if curl -s http://localhost:9997 &> /dev/null; then
            print_success "Batfish is running and responding"
            return 0
        fi
        print_info "Waiting for Batfish API... ($i/$max_attempts)"
        sleep 10
    done
    
    print_warning "Batfish container started but API not responding yet"
    print_info "This is normal. Batfish may need more time to initialize."
    print_info "You can check status with: systemctl status batfish"
}

# Uninstall Batfish
uninstall_batfish() {
    print_header "Uninstalling Batfish"
    
    # Stop and disable service
    systemctl stop batfish 2>/dev/null || true
    systemctl disable batfish 2>/dev/null || true
    
    # Remove systemd service
    rm -f /etc/systemd/system/batfish.service
    systemctl daemon-reload
    
    # Stop and remove container
    if [[ "$RUNTIME" == "docker" ]]; then
        docker stop batfish 2>/dev/null || true
        docker rm batfish 2>/dev/null || true
        docker rmi batfish/batfish:latest 2>/dev/null || true
    else
        podman stop batfish 2>/dev/null || true
        podman rm batfish 2>/dev/null || true
        podman rmi batfish/batfish:latest 2>/dev/null || true
    fi
    
    print_success "Batfish uninstalled"
}

# Setup Tier 2: Containerlab
setup_containerlab() {
    print_header "Setting up Tier 2: Containerlab (Emulation)"
    
    # Install Containerlab
    print_info "Installing Containerlab..."
    
    # Use the official containerlab install script with all features
    # This handles architecture detection and proper download
    curl -sL https://containerlab.dev/setup | sudo -E bash -s "all"
    
    # Verify installation
    if command -v containerlab &> /dev/null; then
        print_success "Containerlab installed successfully"
        containerlab version 2>/dev/null | head -2 || true
    else
        print_error "Containerlab installation failed"
        return 1
    fi
    
    # Create containerlab directories
    mkdir -p /etc/containerlab
    mkdir -p /var/lib/containerlab
    
    # Test Docker/Podman access
    print_info "Testing container runtime access..."
    if [[ "$RUNTIME" == "docker" ]]; then
        docker ps &> /dev/null && print_success "Docker access confirmed"
    else
        podman ps &> /dev/null && print_success "Podman access confirmed"
    fi
    
    print_success "Containerlab is ready to use"
    print_info "Usage: containerlab deploy -t <topology-file>"
}

# Uninstall Containerlab
uninstall_containerlab() {
    print_header "Uninstalling Containerlab"
    
    # Remove binary
    rm -f /usr/local/bin/containerlab
    
    # Remove directories
    rm -rf /etc/containerlab
    rm -rf /var/lib/containerlab
    
    print_success "Containerlab uninstalled"
}

# Setup Tier 3: GNS3
setup_gns3() {
    print_header "Setting up Tier 3: GNS3 (Simulation)"
    
    # Add GNS3 PPA
    print_info "Adding GNS3 PPA..."
    add-apt-repository -y ppa:gns3/ppa
    pkg_update
    
    # Install GNS3 server and dependencies
    print_info "Installing GNS3 Server..."
    pkg_install \
        gns3-server \
        ubridge \
        qemu-kvm \
        qemu-utils \
        qemu-system-x86 \
        libvirt-clients \
        libvirt-daemon-system \
        virtinst \
        bridge-utils \
        cpu-checker
    
    # Configure permissions
    print_info "Configuring permissions..."
    if [[ -n "$SUDO_USER" ]]; then
        usermod -aG kvm,libvirt,ubridge,docker "$SUDO_USER" 2>/dev/null || true
        usermod -aG kvm,libvirt,ubridge "$SUDO_USER"
    fi
    
    # Set ubridge permissions
    chmod u+s /usr/bin/ubridge
    
    # Configure GNS3 to use Docker
    mkdir -p /etc/gns3
    cat > /etc/gns3/gns3_server.conf << EOF
[Server]
host = 0.0.0.0
port = 3080

[Docker]
enabled = true
EOF
    
    # Create systemd service for GNS3
    cat > /etc/systemd/system/gns3-server.service << EOF
[Unit]
Description=GNS3 Server
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/gns3server
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and start GNS3
    systemctl daemon-reload
    systemctl enable gns3-server
    systemctl start gns3-server
    
    # Check KVM support
    print_info "Checking KVM support..."
    if kvm-ok &> /dev/null; then
        print_success "KVM is supported and enabled"
    else
        print_warning "KVM may not be fully supported"
        print_info "For nested virtualization, ensure it's enabled in BIOS"
    fi
    
    # Wait for GNS3 to start
    sleep 3
    
    # Verify GNS3 is running
    if systemctl is-active --quiet gns3-server; then
        print_success "GNS3 Server is running on port 3080"
    else
        print_warning "GNS3 Server service started but may not be fully ready"
        print_info "Check status with: systemctl status gns3-server"
    fi
}

# Uninstall GNS3
uninstall_gns3() {
    print_header "Uninstalling GNS3"
    
    # Stop and disable service
    systemctl stop gns3-server 2>/dev/null || true
    systemctl disable gns3-server 2>/dev/null || true
    
    # Remove systemd service
    rm -f /etc/systemd/system/gns3-server.service
    systemctl daemon-reload
    
    # Remove GNS3 packages
    pkg_purge gns3-server ubridge qemu-kvm qemu-utils qemu-system-x86
    
    # Remove GNS3 PPA
    add-apt-repository --remove -y ppa:gns3/ppa 2>/dev/null || true
    
    # Remove configuration
    rm -rf /etc/gns3
    rm -rf /var/lib/GNS3
    
    print_success "GNS3 uninstalled"
}

# Verify installation
verify_installation() {
    print_header "Verifying Installation"
    
    local all_good=true
    
    # Check runtime
    if [[ "$RUNTIME" == "docker" ]]; then
        if docker info &> /dev/null; then
            print_success "Docker is running"
        else
            print_error "Docker is not running"
            all_good=false
        fi
    else
        if podman info &> /dev/null; then
            print_success "Podman is running"
        else
            print_error "Podman is not running"
            all_good=false
        fi
    fi
    
    # Check Tier 1: Batfish
    if [[ "$TIERS" == "all" || "$TIERS" == *"1"* ]]; then
        if curl -s http://localhost:9997 &> /dev/null; then
            print_success "Tier 1: Batfish is responding on port 9997"
        else
            print_error "Tier 1: Batfish is not responding"
            print_info "Start with: systemctl start batfish"
            all_good=false
        fi
    fi
    
    # Check Tier 2: Containerlab
    if [[ "$TIERS" == "all" || "$TIERS" == *"2"* ]]; then
        if command -v containerlab &> /dev/null; then
            local version=$(containerlab version 2>/dev/null | head -1)
            print_success "Tier 2: Containerlab is installed ($version)"
        else
            print_error "Tier 2: Containerlab is not installed"
            all_good=false
        fi
    fi
    
    # Check Tier 3: GNS3
    if [[ "$TIERS" == "all" || "$TIERS" == *"3"* ]]; then
        if systemctl is-active --quiet gns3-server 2>/dev/null; then
            print_success "Tier 3: GNS3 Server is running on port 3080"
        else
            print_error "Tier 3: GNS3 Server is not running"
            print_info "Start with: systemctl start gns3-server"
            all_good=false
        fi
    fi
    
    echo ""
    if [[ "$all_good" == true ]]; then
        print_success "All validators are installed and running!"
    else
        print_warning "Some validators are not running. Check the messages above."
    fi
    
    return 0
}

# Show next steps
show_next_steps() {
    echo ""
    print_header "Installation Complete!"
    echo ""
    echo "Your three-tier validators are now installed:"
    echo ""
    
    if [[ "$TIERS" == "all" || "$TIERS" == *"1"* ]]; then
        echo "Tier 1 - Batfish (Static Analysis):"
        echo "  - API Endpoint: http://localhost:9997"
        echo "  - Service: systemctl status batfish"
        echo "  - Logs: journalctl -u batfish -f"
        echo ""
    fi
    
    if [[ "$TIERS" == "all" || "$TIERS" == *"2"* ]]; then
        echo "Tier 2 - Containerlab (Emulation):"
        echo "  - Binary: /usr/local/bin/containerlab"
        echo "  - Version: containerlab version"
        echo "  - Deploy: containerlab deploy -t topology.yml"
        echo ""
    fi
    
    if [[ "$TIERS" == "all" || "$TIERS" == *"3"* ]]; then
        echo "Tier 3 - GNS3 (Simulation):"
        echo "  - API Endpoint: http://localhost:3080"
        echo "  - Service: systemctl status gns3-server"
        echo "  - Connect GNS3 GUI to: Host: localhost, Port: 3080"
        echo ""
    fi
    
    echo "Management Commands:"
    echo "  - Verify: sudo ./install_validators_ubuntu.sh --verify"
    echo "  - View logs: journalctl -u <service-name> -f"
    echo "  - Start/Stop: systemctl start|stop <service-name>"
    echo ""
    
    if [[ -n "$SUDO_USER" ]]; then
        print_warning "IMPORTANT: Log out and log back in for group permissions to take effect"
        echo "  (Or run: newgrp docker)"
        echo ""
    fi
    
    print_info "You can now run the RAG-NetTwin evaluation:"
    echo "  uv run python src/evaluation/evaluator.py"
    echo ""
}

# Main installation flow
main() {
    parse_args "$@"
    
    print_header "RAG-NetTwin Three-Tier Validator Installation"
    echo "Package Manager: ${PKG_MANAGER}"
    echo "Container Runtime: ${RUNTIME:-'Auto-detect'}"
    echo "Installation Mode: ${UNINSTALL_MODE:+uninstall}${VERIFY_MODE:+verify}${UNINSTALL_MODE:-${VERIFY_MODE:-install}}"
    echo "Tiers: ${TIERS}"
    echo ""
    
    # Check root
    check_root
    
    # Handle uninstall mode
    if [[ "$UNINSTALL_MODE" == true ]]; then
        detect_runtime || {
            print_warning "No container runtime detected, using default runtime detection"
        }
        
        confirm_uninstallation
        
        if [[ "$DRY_RUN" == true ]]; then
            exit 0
        fi
        
        # Uninstall tiers
        if [[ "$TIERS" == "all" || "$TIERS" == *"3"* ]]; then
            uninstall_gns3
        fi
        
        if [[ "$TIERS" == "all" || "$TIERS" == *"2"* ]]; then
            uninstall_containerlab
        fi
        
        if [[ "$TIERS" == "all" || "$TIERS" == *"1"* ]]; then
            uninstall_batfish
        fi
        
        # Optionally uninstall runtime (only if uninstalling all tiers)
        if [[ "$TIERS" == "all" ]]; then
            echo ""
            read -p "Also uninstall container runtime ($RUNTIME)? [y/N]: " uninstall_runtime
            if [[ "$uninstall_runtime" =~ ^[Yy]$ ]]; then
                if [[ "$RUNTIME" == "docker" ]]; then
                    uninstall_docker
                elif [[ "$RUNTIME" == "podman" ]]; then
                    uninstall_podman
                fi
            fi
        fi
        
        print_success "Uninstallation complete!"
        exit 0
    fi
    
    # Verify mode
    if [[ "$VERIFY_MODE" == true ]]; then
        detect_runtime || {
            print_error "No container runtime detected"
            exit 1
        }
        verify_installation
        exit 0
    fi
    
    # Detect or prompt for runtime
    if [[ -z "$RUNTIME" ]]; then
        if ! detect_runtime; then
            prompt_runtime_choice
        fi
    fi
    
    # Show summary and confirm
    confirm_installation
    
    if [[ "$DRY_RUN" == true ]]; then
        exit 0
    fi
    
    # Install container runtime
    if [[ "$RUNTIME" == "docker" ]]; then
        if ! command -v docker &> /dev/null; then
            install_docker
        fi
    else
        if ! command -v podman &> /dev/null; then
            install_podman
        fi
    fi
    
    # Install tiers
    if [[ "$TIERS" == "all" || "$TIERS" == *"1"* ]]; then
        setup_batfish
    fi
    
    if [[ "$TIERS" == "all" || "$TIERS" == *"2"* ]]; then
        setup_containerlab
    fi
    
    if [[ "$TIERS" == "all" || "$TIERS" == *"3"* ]]; then
        setup_gns3
    fi
    
    # Verify installation
    verify_installation
    
    # Show next steps
    show_next_steps
}

# Run main function
main "$@"
