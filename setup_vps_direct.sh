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
echo "[2/4] Setting up Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Install Python requirements
echo "[3/4] Installing Python packages from requirements_vps.txt..."
pip install --upgrade pip
pip install -r requirements_vps.txt

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
echo "      ./.venv/bin/python vps_relay.py"
echo "   (enter your phone and OTP code once)"
echo "3. Start 24/7 background mode:"
echo "      ./start_vps.sh"
echo "=================================================================="
