#!/bin/bash
# ------------------------------------------------------------------
# Jarvis 24/7 Background Runner with Auto-Restart (No Systemd required)
# Works inside Docker, Containers, WSL, and all Linux VPS
# ------------------------------------------------------------------

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "jarvis.pid" ]; then
    PID=$(cat jarvis.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "[Jarvis VPS] Jarvis is already running with PID $PID."
        exit 0
    else
        rm -f jarvis.pid
    fi
fi

PYTHON_BIN="./.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    if [ -f "/root/jarvis_venv/bin/python" ]; then
        PYTHON_BIN="/root/jarvis_venv/bin/python"
    elif [ -f "$HOME/.jarvis_venv/bin/python" ]; then
        PYTHON_BIN="$HOME/.jarvis_venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    fi
fi

echo "[Jarvis VPS] Using Python: $PYTHON_BIN"
echo "[Jarvis VPS] Starting Jarvis 24/7 background relay with auto-restart..."
nohup bash -c "
    while true; do
        echo \"[Jarvis VPS] Process started at \$(date)\" >> jarvis.log
        \"$PYTHON_BIN\" vps_relay.py >> jarvis.log 2>&1
        EXIT_CODE=\$?
        echo \"[Jarvis VPS] Process exited with code \$EXIT_CODE at \$(date). Restarting in 3s...\" >> jarvis.log
        sleep 3
    done
" >/dev/null 2>&1 &

echo $! > jarvis.pid
sleep 1

if [ -f "jarvis.pid" ] && kill -0 "$(cat jarvis.pid)" 2>/dev/null; then
    echo "=================================================================="
    echo "✅ Jarvis 24/7 is now running in the background! (PID: $(cat jarvis.pid))"
    echo "Check live logs:  tail -f jarvis.log"
    echo "Check status:     ./status_vps.sh"
    echo "Stop service:     ./stop_vps.sh"
    echo "=================================================================="
else
    echo "❌ Failed to start Jarvis. Check jarvis.log for details."
fi
