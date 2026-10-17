#!/bin/bash
# ------------------------------------------------------------------
# Jarvis 24/7 Direct VPS Setup for Ubuntu / Debian (Fresh Deployment)
# ------------------------------------------------------------------

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================================="
echo "⚡ Jarvis 24/7 VPS Deployment - Initializing Setup"
echo "=================================================================="

# Install apt packages
echo "[1/4] Installing system dependencies (python3, ffmpeg, git, psmisc)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y python3 python3-pip python3-venv ffmpeg git curl psmisc
else
    echo "Notice: Non-Debian/Ubuntu system. Please ensure python3, ffmpeg, and git are installed."
fi

# Setup Virtual Environment
echo "[2/4] Setting up Python virtual environment..."
VENV_DIR=".venv"

rm -rf .venv 2>/dev/null || true

HAS_SYMLINK=1
python3 -m venv .venv 2>/dev/null || HAS_SYMLINK=0

if [ "$HAS_SYMLINK" -eq 1 ] && [ -f ".venv/bin/activate" ]; then
    VENV_DIR=".venv"
else
    echo "[!] Current filesystem does not support symlinks (Errno 38)."
    echo "[!] Creating virtual environment in /root/jarvis_venv instead..."
    rm -rf .venv 2>/dev/null || true
    VENV_DIR="/root/jarvis_venv"
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        VENV_DIR="$HOME/.jarvis_venv"
        python3 -m venv "$VENV_DIR" 2>/dev/null || true
    fi
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate" 2>/dev/null || . "$VENV_DIR/bin/activate"
    PIP_CMD="$VENV_DIR/bin/pip"
    PYTHON_CMD="$VENV_DIR/bin/python"
else
    echo "[!] Fallback: using system pip with --break-system-packages..."
    PIP_CMD="pip"
    PYTHON_CMD="python3"
fi

# Install Python requirements
echo "[3/4] Installing Python packages from requirements_vps.txt..."
$PIP_CMD install --upgrade pip 2>/dev/null || true
$PIP_CMD install --break-system-packages -r requirements_vps.txt 2>/dev/null || $PIP_CMD install -r requirements_vps.txt

# Ensure shell scripts are executable
echo "[4/4] Setting script permissions..."
chmod +x *.sh 2>/dev/null || true

# Config placeholder if missing
mkdir -p config
if [ ! -f "config/api_keys.json" ]; then
    echo "[!] config/api_keys.json not found. Creating placeholder..."
    cat << 'EOF' > config/api_keys.json
{
    "gemini_api_key": "",
    "telegram_api_id": 0,
    "telegram_api_hash": "",
    "openrouter_api_key": ""
}
EOF
fi

echo "=================================================================="
echo "✅ Setup successfully completed!"
echo "------------------------------------------------------------------"
echo "📌 Next Steps:"
echo "1. Put your api_keys.json in config/api_keys.json"
echo "2. If you have jarvis.session, copy it to $(pwd)/jarvis.session"
echo "   OR if logging in for the first time on this VPS, run:"
echo "      ./run_interactive.sh"
echo "      (or: $PYTHON_CMD vps_relay.py)"
echo "   (enter your phone and OTP code once)"
echo "3. Start 24/7 background mode:"
echo "      ./start_vps.sh"
echo "=================================================================="

