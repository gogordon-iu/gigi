#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

# Get the directory of this script and locate start_bluetooth_hub.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HUB_SCRIPT="$SCRIPT_DIR/start_bluetooth_hub.sh"

echo "============================================================"
echo "      Gigi Robotics Bluetooth Hub Startup Installer"
echo "============================================================"

# 1. Ensure running as root
if [ "$EUID" -ne 0 ]; then
  echo "[!] Error: This script must be run as root. Please run with sudo:"
  echo "    sudo $0"
  exit 1
fi

# 2. Make hub scripts executable
echo "[*] Setting executable permissions on scripts..."
chmod +x "$HUB_SCRIPT"
chmod +x "$SCRIPT_DIR/bt_agent.py"
chmod +x "$SCRIPT_DIR/bt_listener.py"

# 3. Create the systemd service file
SERVICE_PATH="/etc/systemd/system/gigi-bluetooth.service"
echo "[*] Creating systemd service at $SERVICE_PATH..."

cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=Gigi Robotics Bluetooth Hub
After=bluetooth.target systemd-suspend.service
Requires=bluetooth.target

[Service]
Type=oneshot
ExecStart=$HUB_SCRIPT
RemainAfterExit=yes
User=root
WorkingDirectory=$SCRIPT_DIR

[Install]
WantedBy=multi-user.target
EOF

# 4. Create the suspend/resume wakeup script hook
SLEEP_HOOK_PATH="/lib/systemd/system-sleep/gigi-bluetooth"
echo "[*] Creating sleep/wake hook at $SLEEP_HOOK_PATH..."

cat <<EOF > "$SLEEP_HOOK_PATH"
#!/bin/sh
case \$1/\$2 in
  post/*)
    echo "Gigi Bluetooth Hub: System woke up, restarting service..." >> /var/log/gigi-bluetooth-sleep.log 2>&1
    systemctl restart gigi-bluetooth.service >> /var/log/gigi-bluetooth-sleep.log 2>&1
    ;;
esac
EOF

chmod +x "$SLEEP_HOOK_PATH"

# 5. Reload systemd daemon and enable service
echo "[*] Enabling and starting gigi-bluetooth systemd service..."
systemctl daemon-reload
systemctl enable gigi-bluetooth.service
systemctl restart gigi-bluetooth.service

echo "============================================================"
echo " SUCCESS: Bluetooth Hub is configured to start on boot"
echo "          and restart automatically upon waking from sleep!"
echo "============================================================"
echo "You can check status using:"
echo "    sudo systemctl status gigi-bluetooth.service"
echo "View logs using:"
echo "    sudo journalctl -u gigi-bluetooth.service -f"
echo "============================================================"
