#!/usr/bin/env bash

# Exit on error
set -e

echo "============================================================"
echo "      Gigi BlueZ Bluetooth compatibility & SPP Fixer"
echo "============================================================"

# 1. Ensure running as root
if [ "$EUID" -ne 0 ]; then
  echo "[!] Error: This script must be run as root. Please run with sudo:"
  echo "    sudo $0"
  exit 1
fi

# 2. Check if bluetooth.service exists
SERVICE_FILE="/lib/systemd/system/bluetooth.service"
if [ ! -f "$SERVICE_FILE" ]; then
  # Fallback to alternative systemd path
  SERVICE_FILE="/etc/systemd/system/dbus-org.bluez.service"
fi

if [ -f "$SERVICE_FILE" ]; then
  echo "[*] Found bluetooth service file at: $SERVICE_FILE"
  
  # Check if compatibility flag -C or --compat is already present
  if grep -q -E "bluetoothd.*(-C|--compat)" "$SERVICE_FILE"; then
    echo "[*] Compatibility mode (-C) is already configured in systemd."
  else
    echo "[*] Adding compatibility flag (-C) to bluetoothd command..."
    # Replace ExecStart=/usr/lib/bluetooth/bluetoothd with ExecStart=/usr/lib/bluetooth/bluetoothd -C
    # We use sed to safely modify the line
    sed -i 's|ExecStart=/usr/lib/bluetooth/bluetoothd|ExecStart=/usr/lib/bluetooth/bluetoothd -C|g' "$SERVICE_FILE"
    echo "    -> Modified ExecStart in $SERVICE_FILE"
    
    # Reload and restart bluetooth
    echo "[*] Reloading systemd daemon and restarting Bluetooth service..."
    systemctl daemon-reload
    systemctl restart bluetooth
  fi
else
  echo "[!] Error: Could not locate BlueZ systemd service file."
  exit 1
fi

# 3. Add Serial Port service class to SDP
echo "[*] Registering Serial Port Profile (SPP)..."
if sdptool add SP; then
  echo "    -> SPP registered successfully!"
else
  echo "[!] Warning: sdptool add SP failed. Please check if bluetoothd is running in compatibility mode."
fi

# 4. Restart the Gigi Bluetooth Hub
echo "[*] Restarting gigi-bluetooth service..."
if systemctl list-unit-files | grep -q "gigi-bluetooth.service"; then
  systemctl restart gigi-bluetooth.service
  echo "    -> gigi-bluetooth service restarted!"
else
  # If running manually, launch the hub script
  SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
  if [ -f "$SCRIPT_DIR/start_bluetooth_hub.sh" ]; then
    echo "[*] Running start_bluetooth_hub.sh..."
    bash "$SCRIPT_DIR/start_bluetooth_hub.sh"
  fi
fi

echo "============================================================"
echo " SUCCESS: BlueZ Compatibility fixed and SPP registered!"
echo " Please UNPAIR and RE-PAIR the robot in your phone's settings"
echo " so Android can query the new Serial Port Profile (SPP)."
echo "============================================================"
