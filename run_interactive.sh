#!/bin/bash
# ------------------------------------------------------------------
# Jarvis VPS Interactive Runner (for initial Telegram OTP login / testing)
# ------------------------------------------------------------------

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

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

echo "[Jarvis VPS] Launching interactive relay using: $PYTHON_BIN"
exec "$PYTHON_BIN" vps_relay.py "$@"
