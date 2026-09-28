#!/usr/bin/env bash
# ==============================================================================
# Gigi Factory Sanitization & Golden Image Preparation Script
# ==============================================================================
# WARNING: This script prepares the physical robot for golden eMMC disk cloning.
# It scrubs all developer-specific credentials, private Wi-Fi networks,
# Bluetooth pairings, personal SSH keys, and system logs.
#
# DO NOT RUN THIS UNTIL YOU ARE READY TO CAPTURE THE EMMC IMAGE!
# Once executed, Wi-Fi will disconnect and the robot will safely power down.
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "[!] Error: This script must be run as root (e.g. sudo bash Setup/prepare_factory_image.sh)"
  exit 1
fi

echo "======================================================================"
echo "    GIGI ROBOTICS: PREPARING GOLDEN DISTRIBUTABLE EMMC IMAGE"
echo "======================================================================"

# 1. Stop background services cleanly
echo "[1/7] Stopping running background services..."
systemctl stop gigi-bluetooth.service || true
pkill -f "alive_mode.py" || true
pkill -f "bt_listener.py" || true
pkill -f "bt_agent.py" || true
pkill -f "rfcomm" || true
pkill -f "flask_server.py" || true

# 2. Scrub Private Saved Wi-Fi Networks
echo "[2/7] Removing saved Wi-Fi connections and credentials..."
rm -f /etc/NetworkManager/system-connections/*.nmconnection || true
systemctl restart NetworkManager || true

# 3. Scrub Bluetooth Paired Device Database
echo "[3/7] Clearing paired Bluetooth device cache..."
rm -rf /var/lib/bluetooth/* || true

# 4. Scrub SSH Keys
echo "[4/7] Clearing authorized SSH keys and developer host keys..."
rm -f /home/orangepi/.ssh/authorized_keys || true
rm -f /root/.ssh/authorized_keys || true
rm -f /etc/ssh/ssh_host_* || true

# 5. Scrub Local Motor Calibration (Force uncalibrated safe state for new robot hardware)
echo "[5/8] Removing robot-specific motor calibrations & old repos..."
rm -f /home/orangepi/Code/gigi/motorData_calibrated.json || true
rm -f /home/orangepi/Code/gigi/motorData_calibrated_local.json || true
rm -f /home/orangepi/Code/gigi/Character/motorData_calibrated.json || true
rm -f /home/orangepi/Code/gigi/Character/motorData_calibrated_local.json || true
rm -rf /home/orangepi/repos || true

# 6. Scrub System Logs, Application Session Data, and Shell History
echo "[6/8] Clearing logs, user session data, and shell history..."
rm -rf /home/orangepi/Code/gigi/Logs/* || true
rm -rf /home/orangepi/Code/gigi/data/users/* || true
find /var/log -type f -exec truncate -s 0 {} + 2>/dev/null || true
journalctl --vacuum-time=1s || true
cat /dev/null > /home/orangepi/.bash_history || true
cat /dev/null > /root/.bash_history || true
history -c || true

# 7. Purge Package Manager & Runtime Caches
echo "[7/8] Purging package manager and runtime caches..."
apt-get clean || true
apt-get autoremove -y || true
rm -rf /tmp/* /var/tmp/* || true
rm -rf /home/orangepi/.cache/* /root/.cache/* || true

# 8. Discard Unused Blocks (eMMC TRIM for maximum disk image compression)
echo "[8/8] Zeroing unused filesystem blocks with fstrim..."
fstrim -av || true

echo "======================================================================"
echo "  [SUCCESS] Gigi has been sanitized and prepared for disk cloning!"
echo "  Shutting down in 5 seconds. Pull the eMMC or boot from SD card to"
echo "  dump the golden image."
echo "======================================================================"
sleep 5
shutdown -h now
