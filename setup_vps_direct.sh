#!/bin/bash
# ------------------------------------------------------------------
# Jarvis 24/7 Direct VPS Setup (No Docker) for Ubuntu 24.04
# ------------------------------------------------------------------

set -e

echo "[Jarvis VPS] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv ffmpeg git portaudio19-dev libgl1 libglib2.0-0 xvfb

echo "[Jarvis VPS] Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[Jarvis VPS] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements_docker.txt

chmod +x start_vps.sh stop_vps.sh status_vps.sh 2>/dev/null || true

# Check if running in a systemd environment (PID 1 is systemd)
if [ -d /run/systemd/system ] && pidof systemd >/dev/null 2>&1; then
    echo "[Jarvis VPS] Systemd detected. Configuring 24/7 Systemd Background Service..."
    CURRENT_DIR=$(pwd)

    cat <<EOF > /etc/systemd/system/jarvis.service
[Unit]
Description=Jarvis AI Assistant 24/7 Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/.venv/bin/python vps_relay.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    echo "[Jarvis VPS] Enabling and starting Jarvis service..."
    systemctl daemon-reload
    systemctl enable --now jarvis

    echo "=================================================================="
    echo "[OK] Jarvis is now running 24/7 on your VPS via systemd!"
    echo "Check live logs: sudo journalctl -u jarvis -f"
    echo "Check status:    sudo systemctl status jarvis"
    echo "Restart service: sudo systemctl restart jarvis"
    echo "=================================================================="
else
    echo "[Jarvis VPS] Container / Non-systemd environment detected."
    echo "[Jarvis VPS] Starting Jarvis 24/7 background supervisor..."
    ./start_vps.sh
fi
