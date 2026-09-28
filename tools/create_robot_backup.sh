#!/usr/bin/env bash
# ==============================================================================
# Helper Script to Archive All Robot Items Before Sanitization
# ==============================================================================

set -e

BACKUP_DIR="/tmp/robot_backup_staging"
OUTPUT_TAR="/home/orangepi/gigi_pre_sanitization_backup.tar.gz"

echo "[*] Staging items to backup..."
rm -rf "$BACKUP_DIR" "$OUTPUT_TAR"
mkdir -p "$BACKUP_DIR/network_system_connections"
mkdir -p "$BACKUP_DIR/bluetooth_pairing_database"
mkdir -p "$BACKUP_DIR/ssh_host_keys"
mkdir -p "$BACKUP_DIR/user_ssh"
mkdir -p "$BACKUP_DIR/logs"
mkdir -p "$BACKUP_DIR/user_data"
mkdir -p "$BACKUP_DIR/motor_calibration"
mkdir -p "$BACKUP_DIR/shell_and_environment"

# 1. Wi-Fi connections
cp -rf /etc/NetworkManager/system-connections/* "$BACKUP_DIR/network_system_connections/" 2>/dev/null || true

# 2. Bluetooth pairing database
cp -rf /var/lib/bluetooth/* "$BACKUP_DIR/bluetooth_pairing_database/" 2>/dev/null || true

# 3. SSH host keys
cp -f /etc/ssh/ssh_host_* "$BACKUP_DIR/ssh_host_keys/" 2>/dev/null || true

# 4. User SSH keys
cp -rf /home/orangepi/.ssh/* "$BACKUP_DIR/user_ssh/" 2>/dev/null || true

# 5. Shell history & environment
cp -f /home/orangepi/.bash_history "$BACKUP_DIR/shell_and_environment/orangepi_bash_history" 2>/dev/null || true
cp -f /root/.bash_history "$BACKUP_DIR/shell_and_environment/root_bash_history" 2>/dev/null || true
cp -f /home/orangepi/.bashrc "$BACKUP_DIR/shell_and_environment/orangepi_bashrc" 2>/dev/null || true
cp -f /etc/environment "$BACKUP_DIR/shell_and_environment/etc_environment" 2>/dev/null || true

# 6. Application Logs
cp -rf /home/orangepi/Code/gigi/Logs/* "$BACKUP_DIR/logs/" 2>/dev/null || true

# 7. User Data Sessions
cp -rf /home/orangepi/Code/gigi/data/* "$BACKUP_DIR/user_data/" 2>/dev/null || true

# 8. Physical Motor Calibration
cp -f /home/orangepi/Code/gigi/motorData_calibrated*.json "$BACKUP_DIR/motor_calibration/" 2>/dev/null || true

# 9. System state snapshots
nmcli connection show > "$BACKUP_DIR/network_system_connections/active_connections_summary.txt" 2>/dev/null || true
bluetoothctl devices > "$BACKUP_DIR/bluetooth_pairing_database/paired_devices_summary.txt" 2>/dev/null || true
ip addr > "$BACKUP_DIR/network_system_connections/ip_addr_snapshot.txt" 2>/dev/null || true
hostnamectl > "$BACKUP_DIR/shell_and_environment/hostnamectl_snapshot.txt" 2>/dev/null || true

echo "[*] Creating tar archive: $OUTPUT_TAR..."
tar -czf "$OUTPUT_TAR" -C "$BACKUP_DIR" .
chown orangepi:orangepi "$OUTPUT_TAR"
rm -rf "$BACKUP_DIR"

echo "[*] Backup complete: $(ls -lh "$OUTPUT_TAR" | awk '{print $5, $9}')"
