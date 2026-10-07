#!/usr/bin/env bash
# ==============================================================================
# Gigi Robotics: External eMMC Post-Test Sanitization & Golden Image Prep
# ==============================================================================
# Use this script when the newly cloned eMMC has been tested on physical hardware
# and is now connected via USB reader to the host system.
#
# This sanitizes the external eMMC WITHOUT re-cloning or overwriting its code,
# removing test Wi-Fi credentials, Bluetooth keys, SSH keys, logs, and history.
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: This script must be run as root (e.g. sudo bash Setup/sanitize_external_emmc.sh)"
    exit 1
fi

echo "======================================================================"
echo "    GIGI ROBOTICS: EXTERNAL EMMC POST-TEST SANITIZATION"
echo "======================================================================"

# Determine target disk
TARGET_DEV="${1:-/dev/sda}"
MOUNT_POINT="/mnt/target_emmc"

if [ ! -b "$TARGET_DEV" ]; then
    echo "[!] Error: Target block device $TARGET_DEV not found!"
    echo "    Usage: sudo bash $0 [/dev/sdX]"
    echo "    Available disks:"
    lsblk -d -o NAME,SIZE,MODEL,TRAN
    exit 1
fi

echo "[*] Target device selected: $TARGET_DEV"
lsblk "$TARGET_DEV"

# Identify rootfs partition (usually partition 2)
if [ -b "${TARGET_DEV}2" ]; then
    ROOT_PART="${TARGET_DEV}2"
elif [ -b "${TARGET_DEV}p2" ]; then
    ROOT_PART="${TARGET_DEV}p2"
else
    echo "[!] Error: Could not locate partition 2 on $TARGET_DEV"
    exit 1
fi

echo "[*] Root partition identified: $ROOT_PART"

# 1. Mount target rootfs
echo "[1/8] Mounting $ROOT_PART to $MOUNT_POINT..."
mkdir -p "$MOUNT_POINT"
umount "$MOUNT_POINT" 2>/dev/null || true
mount "$ROOT_PART" "$MOUNT_POINT"

# Verify filesystem layout
if [ ! -d "$MOUNT_POINT/home/orangepi/Code/gigi" ]; then
    echo "[!] Error: $MOUNT_POINT does not appear to contain a valid Gigi installation!"
    umount "$MOUNT_POINT"
    exit 1
fi

# 2. Scrub Private Saved Wi-Fi Networks
echo "[2/8] Removing saved Wi-Fi networks and passwords..."
rm -f "$MOUNT_POINT"/etc/NetworkManager/system-connections/* 2>/dev/null || true

# 3. Scrub Bluetooth Paired Device Database
echo "[3/8] Clearing Bluetooth pairing records and link keys..."
rm -rf "$MOUNT_POINT"/var/lib/bluetooth/* 2>/dev/null || true

# Verify bt_agent.py has NoInputNoOutput capability
echo "[*] Ensuring bt_agent.py uses NoInputNoOutput for Just-Works pairing..."
if [ -f "$MOUNT_POINT/home/orangepi/Code/gigi/Setup/bt_agent.py" ]; then
    sed -i 's/agent KeyboardOnly/agent NoInputNoOutput/g' "$MOUNT_POINT/home/orangepi/Code/gigi/Setup/bt_agent.py"
fi

# 4. Scrub SSH Host Keys & Authorized Keys
echo "[4/8] Removing host keys and authorized keys..."
rm -f "$MOUNT_POINT"/home/orangepi/.ssh/authorized_keys* 2>/dev/null || true
rm -f "$MOUNT_POINT"/root/.ssh/authorized_keys* 2>/dev/null || true
rm -f "$MOUNT_POINT"/etc/ssh/ssh_host_* 2>/dev/null || true

# Guarantee first-boot SSH host key generation service override is present
mkdir -p "$MOUNT_POINT"/etc/systemd/system/ssh.service.d
cat << 'OVR_EOF' > "$MOUNT_POINT"/etc/systemd/system/ssh.service.d/override.conf
[Service]
ExecStartPre=
ExecStartPre=/usr/bin/ssh-keygen -A
ExecStartPre=/usr/sbin/sshd -t
OVR_EOF

# 5. Disable Ubuntu release upgrade popups on kiosk desktop
echo "[5/8] Disabling desktop update notifier popups..."
sed -i 's/^Prompt=.*/Prompt=never/' "$MOUNT_POINT"/etc/update-manager/release-upgrades 2>/dev/null || true
rm -f "$MOUNT_POINT"/etc/xdg/autostart/update-notifier.desktop 2>/dev/null || true
chmod -x "$MOUNT_POINT"/usr/bin/check-new-release-gtk 2>/dev/null || true

# 6. Scrub Local Motor Calibration & Robot Data
echo "[6/8] Clearing robot calibration, logs, and session databases..."
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/motorData_calibrated.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/motorData_calibrated_local.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/Character/motorData_calibrated.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/Character/motorData_calibrated_local.json 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/repos 2>/dev/null || true

# Machine ID & logs
truncate -s 0 "$MOUNT_POINT"/etc/machine-id 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/Code/gigi/Logs/* 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/Code/gigi/data/users/* 2>/dev/null || true
find "$MOUNT_POINT"/var/log -type f -exec truncate -s 0 {} + 2>/dev/null || true

# 7. Shell history & runtime caches
echo "[7/8] Purging shell histories and runtime caches..."
cat /dev/null > "$MOUNT_POINT"/home/orangepi/.bash_history 2>/dev/null || true
cat /dev/null > "$MOUNT_POINT"/root/.bash_history 2>/dev/null || true
rm -rf "$MOUNT_POINT"/tmp/* "$MOUNT_POINT"/var/tmp/* 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/.cache/* "$MOUNT_POINT"/root/.cache/* 2>/dev/null || true

# 8. Unmount cleanly and sync
echo "[8/8] Syncing filesystem and unmounting..."
sync
fstrim -v "$MOUNT_POINT" 2>/dev/null || true
umount "$MOUNT_POINT"
sync

echo "======================================================================"
echo "  [SUCCESS] TARGET EMMC SANITIZED AND READY FOR IMAGE DUMP!"
echo "======================================================================"
echo "To create a compressed golden image file, run:"
echo "    sudo dd if=$TARGET_DEV bs=16M status=progress conv=fsync | zstd -T0 -o /home/orangepi/gigi_golden_$(date +%Y%m%d).img.zst"
echo "Or with gzip:"
echo "    sudo dd if=$TARGET_DEV bs=16M status=progress conv=fsync | gzip -c > /home/orangepi/gigi_golden_$(date +%Y%m%d).img.gz"
echo "======================================================================"
