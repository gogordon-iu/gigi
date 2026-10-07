#!/usr/bin/env bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( dirname "$SCRIPT_DIR" )"

# Export X11 display variables so child processes can render GUI windows on the screen
export DISPLAY=:0
export XAUTHORITY="/home/orangepi/.Xauthority"

# Make sure log directory exists
LOG_DIR="$BASE_DIR/Logs"
mkdir -p "$LOG_DIR"

# Activate Python Virtual Environment if it exists
if [ -f "$BASE_DIR/venv/bin/activate" ]; then
  echo "[*] Activating Python virtual environment (venv)..."
  source "$BASE_DIR/venv/bin/activate"
elif [ -f "$BASE_DIR/.venv/bin/activate" ]; then
  echo "[*] Activating Python virtual environment (.venv)..."
  source "$BASE_DIR/.venv/bin/activate"
fi

# Define Python executable path (explicitly using venv/.venv if present)
PYTHON_EXEC="python3"
if [ -f "$BASE_DIR/venv/bin/python" ]; then
  PYTHON_EXEC="$BASE_DIR/venv/bin/python"
elif [ -f "$BASE_DIR/.venv/bin/python" ]; then
  PYTHON_EXEC="$BASE_DIR/.venv/bin/python"
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

# Wait up to 15 seconds for a Bluetooth hardware adapter to initialize
echo "[*] Waiting for Bluetooth hardware adapter to initialize..."
for i in {1..15}; do
  if hciconfig | grep -q "hci"; then
    echo "    -> Bluetooth adapter detected!"
    break
  fi
  sleep 1
done

# Ensure Bluetooth is unblocked and powered on
echo "[*] Ensuring Bluetooth is unblocked and powered on..."
rfkill unblock bluetooth || true
bluetoothctl power on || true
hciconfig hci0 up || true
hciconfig hci0 class 0x000100 || true
hciconfig hci0 piscan || true
sleep 1

# Ensure SSH host keys exist (auto-regenerate on first boot if sanitized for disk cloning)
if [ ! -f /etc/ssh/ssh_host_rsa_key ] || [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  echo "[*] Generating fresh unique SSH host keys for this robot..."
  ssh-keygen -A || true
  systemctl restart ssh || true
fi


# 2. Clean up any existing instances
echo "[*] Cleaning up old processes..."
pkill -f "rfcomm watch" || true
pkill -f "Setup/bt_listener.py" || true
pkill -f "Setup/bt_agent.py" || true
pkill -f "flask_server.py" || true
sleep 1

# 3. Register Serial Port Profile (SPP) in BlueZ
echo "[*] Registering Bluetooth Serial Port Profile (SPP)..."
hciconfig hci0 piscan || true
[ -S /var/run/sdp ] && chmod 777 /var/run/sdp || true
for i in {1..10}; do
  if sdptool add SP > /dev/null 2>&1; then
    echo "    -> Serial Port Profile (SPP) registered successfully!"
    [ -S /var/run/sdp ] && chmod 777 /var/run/sdp || true
    break
  fi
  sleep 1
done

# 4. Start the Auto-Pairing Agent
PIN_DISPLAY="${GIGI_BT_PIN:-198420}"
echo "[*] Starting Bluetooth Auto-Pairing Agent (PIN: $PIN_DISPLAY)..."
"$PYTHON_EXEC" -u "$SCRIPT_DIR/bt_agent.py" > "$LOG_DIR/bt_agent.log" 2>&1 &
AGENT_PID=$!
echo "    -> Agent started in background (PID: $AGENT_PID). Logs: $LOG_DIR/bt_agent.log"

# 5. Start RFCOMM Watcher
echo "[*] Starting RFCOMM Watcher on channel 1..."
rfcomm watch 0 1 > "$LOG_DIR/rfcomm_watch.log" 2>&1 &
WATCHER_PID=$!
echo "    -> RFCOMM Watcher started in background (PID: $WATCHER_PID). Logs: $LOG_DIR/rfcomm_watch.log"

# 6. Start Bluetooth Command Listener
echo "[*] Starting Bluetooth Command Listener..."
"$PYTHON_EXEC" -u "$SCRIPT_DIR/bt_listener.py" > "$LOG_DIR/bt_listener.log" 2>&1 &
LISTENER_PID=$!
echo "    -> Listener started in background (PID: $LISTENER_PID). Logs: $LOG_DIR/bt_listener.log"

# 7. Set NPU/CPU frequencies and start NPU LLM Server if present
FREQ_SCRIPT="$BASE_DIR/Resources/rknn-llm/examples/rkllm_server_demo/rkllm_server/fix_freq_rk3588.sh"
if [ -f "$FREQ_SCRIPT" ]; then
  echo "[*] Setting NPU and CPU frequencies to maximum performance..."
  bash "$FREQ_SCRIPT" || true
fi

LLM_SCRIPT="$BASE_DIR/llm_server.sh"
if [ -f "$LLM_SCRIPT" ]; then
  echo "[*] Starting NPU LLM Server..."
  nohup bash "$LLM_SCRIPT" > "$LOG_DIR/llm_server.log" 2>&1 &
  echo "    -> LLM Server started in background. Logs: $LOG_DIR/llm_server.log"
fi

echo "============================================================"
echo "  All services started successfully in background!"
echo "============================================================"
