#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "jarvis.pid" ]; then
    PID=$(cat jarvis.pid)
    echo "[Jarvis VPS] Stopping Jarvis background supervisor (PID $PID)..."
    pkill -P "$PID" 2>/dev/null || true
    kill -9 "$PID" 2>/dev/null || true
    rm -f jarvis.pid
fi

pkill -f "vps_relay.py" 2>/dev/null || true
echo "=================================================================="
echo "✅ Jarvis 24/7 Service has been stopped."
echo "=================================================================="
