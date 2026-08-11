#!/bin/bash
# ------------------------------------------------------------------
# Jarvis 24/7 VPS Docker Deployment Script for Ubuntu 24.04
# ------------------------------------------------------------------

set -e

echo "[VPS Setup] Updating system packages..."
apt-get update && apt-get install -y git curl docker.io docker-compose-v2

echo "[VPS Setup] Starting & enabling Docker..."
systemctl enable --now docker

echo "[VPS Setup] Cloning repository..."
if [ -d "JarvisAI" ]; then
    cd JarvisAI
    git pull origin multi-agent-a2a
else
    git clone -b multi-agent-a2a https://github.com/parhamje/JarvisAI.git
    cd JarvisAI
fi

echo "[VPS Setup] Building Docker Container..."
docker compose build

echo "[VPS Setup] Starting Jarvis 24/7 Container..."
docker compose up -d

echo "=================================================================="
echo "✅ Jarvis is now deployed & running 24/7 on your Ubuntu VPS!"
echo "Check container status: docker compose ps"
echo "Check live logs:       docker compose logs -f"
echo "=================================================================="
