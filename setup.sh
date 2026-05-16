#!/bin/bash

set -e

echo "========================================="
echo "  CICDSECURITY Setup Script"
echo "========================================="

# Check if running in WSL or Linux
if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
    echo "[INFO] Running in WSL environment"
    IS_WSL=true
else
    echo "[INFO] Running in native Linux environment"
    IS_WSL=false
fi

echo ""
echo "==> Step 1: Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "==> Step 2: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt --break-system-packages

echo "==> Step 3: Installing Security Tools..."

# OpenGrep
echo "  - Installing OpenGrep..."
if command -v opengrep &> /dev/null; then
    echo "    [SKIP] OpenGrep already installed"
else
    curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/main/install.sh | bash || echo "    [WARN] OpenGrep installation failed"
fi

# Slither
echo "  - Installing Slither..."
if command -v slither &> /dev/null; then
    echo "    [SKIP] Slither already installed"
else
    pip install slither-analyzer --break-system-packages || echo "    [WARN] Slither installation failed"
fi

# Trivy
echo "  - Installing Trivy..."
if command -v trivy &> /dev/null; then
    echo "    [SKIP] Trivy already installed"
else
    TRIVY_VERSION="v0.70.0"
    curl -sfL "https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh" | sh -s -- -b /usr/local/bin "$TRIVY_VERSION" || echo "    [WARN] Trivy installation failed"
fi

# TruffleHog
echo "  - Installing TruffleHog..."
if command -v trufflehog &> /dev/null; then
    echo "    [SKIP] TruffleHog already installed"
else
    if command -v go &> /dev/null; then
        go install github.com/trufflesecurity/trufflehog/v3@latest || echo "    [WARN] TruffleHog installation failed"
    else
        echo "    [WARN] Go not found, skipping TruffleHog"
    fi
fi

# ngrok
echo "  - Installing ngrok..."
if command -v ngrok &> /dev/null; then
    echo "    [SKIP] ngrok already installed"
else
    if [ "$IS_WSL" = true ]; then
        echo "    [INFO] Installing ngrok via apt..."
        curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" | sudo tee /etc/apt/sources.list.d/ngrok.list >/dev/null
        sudo apt update -qq
        sudo apt install -y ngrok || echo "    [WARN] ngrok installation failed"
    else
        echo "    [INFO] Downloading ngrok binary..."
        wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -O /tmp/ngrok.tgz
        tar -xzf /tmp/ngrok.tgz -C /usr/local/bin
        rm -f /tmp/ngrok.tgz
    fi
fi

echo ""
echo "==> Step 4: Verifying installations..."
echo ""

verify_tool() {
    local cmd=$1
    local name=$2
    if command -v "$cmd" &> /dev/null; then
        local version=$($cmd --version 2>&1 | head -1 || echo "installed")
        echo "  ✓ $name: $version"
    else
        echo "  ✗ $name: NOT FOUND"
    fi
}

verify_tool git "Git"
verify_tool opengrep "OpenGrep"
verify_tool slither "Slither"
verify_tool trufflehog "TruffleHog"
verify_tool trivy "Trivy"
verify_tool ngrok "ngrok"

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Run: python3 run.py"
echo "  2. Login at: http://localhost:5000"
echo "  3. Default admin: admin / Securepass123@#"
echo ""