#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================================="
echo "JARVIS VPS SERVICE STATUS"
echo "=================================================================="

if [ -f "jarvis.pid" ]; then
    PID=$(cat jarvis.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ Background Supervisor: RUNNING (PID: $PID)"
    else
        echo "⚠️ Background Supervisor: NOT RUNNING (stale PID $PID)"
    fi
else
    echo "ℹ️ Background Supervisor: NOT ACTIVE"
fi

echo ""
echo "--- Python vps_relay Processes ---"
pgrep -a -f "vps_relay.py" || echo "No active vps_relay.py processes found."

echo ""
echo "--- Last 20 lines of jarvis.log ---"
if [ -f "jarvis.log" ]; then
    tail -n 20 jarvis.log
else
    echo "No jarvis.log found yet."
fi
echo "=================================================================="
