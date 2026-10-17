#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "[Jarvis VPS] Restarting Jarvis 24/7 Relay..."
./stop_vps.sh
sleep 1
./start_vps.sh
