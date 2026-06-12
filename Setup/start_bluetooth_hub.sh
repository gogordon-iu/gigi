#!/usr/bin/env bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( dirname "$SCRIPT_DIR" )"

# Make sure log directory exists
LOG_DIR="$BASE_DIR/Logs"
mkdir -p "$LOG_DIR"

# Activate Python Virtual Environment if it exists
if [ -f "$BASE_DIR/venv/bin/activate" ]; then
  echo "[*] Activating Python virtual environment..."
  source "$BASE_DIR/venv/bin/activate"
fi

echo "============================================================"
echo "          Starting Gigi Robotics Bluetooth Hub"
echo "============================================================"
echo "Base Directory: $BASE_DIR"
echo "Log Directory:  $LOG_DIR"

# 1. Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "[!] Warning: This script should ideally run as root (or via sudo)."
  echo "    Some commands like sdptool and rfcomm require root privileges."
fi

# 2. Clean up any existing instances
echo "[*] Cleaning up old processes..."
pkill -f "rfcomm watch" || true
pkill -f "Setup/bt_listener.py" || true
pkill -f "Setup/bt_agent.py" || true
sleep 1

# 3. Register Serial Port Profile (SPP) in BlueZ
echo "[*] Registering Bluetooth Serial Port Profile (SPP)..."
sdptool add SP > /dev/null 2>&1 || true

# 4. Start the Auto-Pairing Agent
echo "[*] Starting Bluetooth Auto-Pairing Agent (PIN: 198420)..."
python3 "$SCRIPT_DIR/bt_agent.py" > "$LOG_DIR/bt_agent.log" 2>&1 &
AGENT_PID=$!
echo "    -> Agent started in background (PID: $AGENT_PID). Logs: $LOG_DIR/bt_agent.log"

# 5. Start RFCOMM Watcher
echo "[*] Starting RFCOMM Watcher on channel 1..."
rfcomm watch 0 1 > "$LOG_DIR/rfcomm_watch.log" 2>&1 &
WATCHER_PID=$!
echo "    -> RFCOMM Watcher started in background (PID: $WATCHER_PID). Logs: $LOG_DIR/rfcomm_watch.log"

# 6. Start Bluetooth Command Listener
echo "[*] Starting Bluetooth Command Listener..."
python3 "$SCRIPT_DIR/bt_listener.py" > "$LOG_DIR/bt_listener.log" 2>&1 &
LISTENER_PID=$!
echo "    -> Listener started in background (PID: $LISTENER_PID). Logs: $LOG_DIR/bt_listener.log"

echo "============================================================"
echo "  All services started successfully in background!"
echo "============================================================"
