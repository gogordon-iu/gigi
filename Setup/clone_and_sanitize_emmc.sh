#!/usr/bin/env bash
set -e

echo '======================================================================'
echo '       GIGI ROBOTICS: eMMC HARDWARE CLONE & SANITIZATION'
echo '======================================================================'

TARGET_DEV="/dev/sda"
SOURCE_DEV="/dev/mmcblk0"
MOUNT_POINT="/mnt/target_emmc"

# 1. Sanity checks
if [ ! -b "$TARGET_DEV" ]; then
    echo "[!] Error: Target device $TARGET_DEV not found!"
    exit 1
fi

SECTORS=$(blockdev --getsz "$TARGET_DEV")
echo "[*] Target device: $TARGET_DEV ($SECTORS sectors)"

if [ "$SECTORS" -lt 120000000 ]; then
    echo "[!] Error: Unexpected disk size for $TARGET_DEV: $SECTORS sectors"
    exit 1
fi

# 2. Disk clone
echo "[*] Starting direct block-level clone from $SOURCE_DEV to $TARGET_DEV..."
echo "[*] Progress will update below (~25-30 minutes at ~35 MB/s):"
dd if="$SOURCE_DEV" of="$TARGET_DEV" bs=16M status=progress conv=fsync

echo "[*] Syncing filesystem caches..."
sync

# 3. Inform kernel of new partitions
echo "[*] Probing partition table on $TARGET_DEV..."
partprobe "$TARGET_DEV" || true
sleep 3

# 4. Mount partition 2 (rootfs)
echo "[*] Mounting ${TARGET_DEV}2 to $MOUNT_POINT..."
mkdir -p "$MOUNT_POINT"
umount "$MOUNT_POINT" 2>/dev/null || true
mount "${TARGET_DEV}2" "$MOUNT_POINT"

# 5. Sanitize target eMMC
echo "[*] Sanitizing target eMMC for factory distribution..."

# Wi-Fi credentials
rm -f "$MOUNT_POINT"/etc/NetworkManager/system-connections/* 2>/dev/null || true

# Bluetooth cache
rm -rf "$MOUNT_POINT"/var/lib/bluetooth/* 2>/dev/null || true

# SSH keys & verify override
rm -f "$MOUNT_POINT"/home/orangepi/.ssh/authorized_keys* 2>/dev/null || true
rm -f "$MOUNT_POINT"/root/.ssh/authorized_keys* 2>/dev/null || true
rm -f "$MOUNT_POINT"/etc/ssh/ssh_host_* 2>/dev/null || true

# Guarantee first-boot SSH host key auto-generator is present
mkdir -p "$MOUNT_POINT"/etc/systemd/system/ssh.service.d
cat << 'OVR_EOF' > "$MOUNT_POINT"/etc/systemd/system/ssh.service.d/override.conf
[Service]
ExecStartPre=
ExecStartPre=/usr/bin/ssh-keygen -A
ExecStartPre=/usr/sbin/sshd -t
OVR_EOF

# Guarantee Gigi Bluetooth Hub and Face Autostart service is present and valid
cat << 'BT_EOF' > "$MOUNT_POINT"/etc/systemd/system/gigi-bluetooth.service
[Unit]
Description=Gigi Robotics Bluetooth Hub
After=bluetooth.service systemd-suspend.service
Requires=bluetooth.service

[Service]
Type=oneshot
ExecStart=/home/orangepi/Code/gigi/Setup/start_bluetooth_hub.sh
RemainAfterExit=yes
User=root
WorkingDirectory=/home/orangepi/Code/gigi/Setup

[Install]
WantedBy=multi-user.target
BT_EOF
chmod 644 "$MOUNT_POINT"/etc/systemd/system/gigi-bluetooth.service

# Disable Ubuntu release upgrade popups on kiosk desktop
sed -i 's/^Prompt=.*/Prompt=never/' "$MOUNT_POINT"/etc/update-manager/release-upgrades 2>/dev/null || true
rm -f "$MOUNT_POINT"/etc/xdg/autostart/update-notifier.desktop 2>/dev/null || true
chmod -x "$MOUNT_POINT"/usr/bin/check-new-release-gtk 2>/dev/null || true

# Remove crash reports and disable Apport problem-report popups
rm -rf "$MOUNT_POINT"/var/crash/* 2>/dev/null || true
if grep -q '^[[:space:]]*enabled[[:space:]]*=' "$MOUNT_POINT"/etc/default/apport 2>/dev/null; then
    sed -i 's/^[[:space:]]*enabled[[:space:]]*=.*/enabled=0/' "$MOUNT_POINT"/etc/default/apport
else
    mkdir -p "$MOUNT_POINT"/etc/default
    printf '\nenabled=0\n' >> "$MOUNT_POINT"/etc/default/apport
fi

# Disable unwanted desktop autostarts
rm -f "$MOUNT_POINT"/etc/xdg/autostart/blueman.desktop \
      "$MOUNT_POINT"/etc/xdg/autostart/xscreensaver.desktop 2>/dev/null || true

# Clear persisted Bluetooth soft-blocks for first boot
for RFKILL_FILE in "$MOUNT_POINT"/var/lib/systemd/rfkill/*bluetooth*; do
    [ -f "$RFKILL_FILE" ] || continue
    printf '0\n' > "$RFKILL_FILE"
done

# Motor calibration (force fresh calibration for new robot body)
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/motorData_calibrated.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/motorData_calibrated_local.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/Character/motorData_calibrated.json 2>/dev/null || true
rm -f "$MOUNT_POINT"/home/orangepi/Code/gigi/Character/motorData_calibrated_local.json 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/repos 2>/dev/null || true

# Legacy archives, developer tool caches, and temporary files
rm -rf "$MOUNT_POINT"/home/orangepi/Code/gigi_legacy_archive \
       "$MOUNT_POINT"/home/orangepi/Code/gigi.git \
       "$MOUNT_POINT"/home/orangepi/Code/Assets \
       "$MOUNT_POINT"/home/orangepi/Code/gigi/Assets/face/themostannoyingprojectididinmylife.zip \
       "$MOUNT_POINT"/home/orangepi/.claude \
       "$MOUNT_POINT"/home/orangepi/.claude.json \
       "$MOUNT_POINT"/home/orangepi/.copilot \
       "$MOUNT_POINT"/home/orangepi/.gemini \
       "$MOUNT_POINT"/home/orangepi/.antigravity-server \
       "$MOUNT_POINT"/home/orangepi/.vscode-server \
       "$MOUNT_POINT"/home/orangepi/clone_output.log \
       "$MOUNT_POINT"/home/orangepi/clone_and_sanitize_emmc.sh 2>/dev/null || true

# Machine ID & logs
truncate -s 0 "$MOUNT_POINT"/etc/machine-id 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/Code/gigi/Logs/* 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/Code/gigi/data/users/* 2>/dev/null || true
find "$MOUNT_POINT"/var/log -type f -exec truncate -s 0 {} + 2>/dev/null || true

# Shell history & caches
cat /dev/null > "$MOUNT_POINT"/home/orangepi/.bash_history 2>/dev/null || true
cat /dev/null > "$MOUNT_POINT"/root/.bash_history 2>/dev/null || true
rm -rf "$MOUNT_POINT"/tmp/* "$MOUNT_POINT"/var/tmp/* 2>/dev/null || true
rm -rf "$MOUNT_POINT"/home/orangepi/.cache/* "$MOUNT_POINT"/root/.cache/* 2>/dev/null || true

# 6. Unmount cleanly
echo "[*] Unmounting $MOUNT_POINT and performing final sync..."
sync
umount "$MOUNT_POINT"
sync

echo '======================================================================'
echo '  [SUCCESS] eMMC MODULE HAS BEEN FLASHED & SANITIZED!'
echo '  You can now safely disconnect this eMMC module.'
echo '======================================================================'
