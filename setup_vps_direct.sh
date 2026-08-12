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

echo "[Jarvis VPS] Creating 24/7 Systemd Background Service..."
CURRENT_DIR=$(pwd)

cat <<EOF > /etc/systemd/system/jarvis.service
[Unit]
Description=Jarvis AI Assistant 24/7 Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${CURRENT_DIR}
ExecStart=/bin/bash -c "Xvfb :99 -screen 0 1280x1024x24 & DISPLAY=:99 ${CURRENT_DIR}/.venv/bin/python main.py"
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
echo "[OK] Jarvis is now running 24/7 on your VPS!"
echo "Check live logs: sudo journalctl -u jarvis -f"
echo "Check status:    sudo systemctl status jarvis"
echo "Restart service: sudo systemctl restart jarvis"
echo "=================================================================="
