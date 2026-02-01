#!/bin/bash
# /home/orangepi/wakeup_gigi.sh
set -euo pipefail

LOG=/home/orangepi/wakeup_gigi.log
echo "=== wakeup_gigi.sh start $(date) ===" >> "$LOG"

# User and paths
USER=orangepi
VENVDIR=/home/orangepi/Code/gigi/venv
PYTHON=${VENVDIR}/bin/python
SCRIPT=/home/orangepi/Code/gigi/Character/wakeUp.py

# X settings
DISPLAY_NUM=":0"
XAUTH=/home/orangepi/.Xauthority
MAX_WAIT_X=60        # seconds to wait for X auth file
MAX_WAIT_USB=60      # seconds to wait for USB audio device

# USB audio detection settings (change if your device differs)
# We will look for any of these strings in `aplay -l` output.
USB_DEVICE_PATTERNS=('card 2:' 'UACDemoV1.0' 'USB Audio')

echo "Waiting for X auth (up to ${MAX_WAIT_X}s)..." >> "$LOG"
i=0
while [ $i -lt $MAX_WAIT_X ]; do
  if [ -f "${XAUTH}" ]; then
    echo "Found X auth ${XAUTH}" >> "$LOG"
    break
  fi
  sleep 1
  i=$((i+1))
done
if [ $i -ge $MAX_WAIT_X ]; then
  echo "Timeout waiting for X auth after ${MAX_WAIT_X}s, continuing anyway" >> "$LOG"
fi

# Export DISPLAY/XAUTH for subsequent commands (xset/xhost)
export DISPLAY=${DISPLAY_NUM}
export XAUTHORITY=${XAUTH}
echo "Using DISPLAY=${DISPLAY}, XAUTHORITY=${XAUTH}" >> "$LOG"

# Prevent screen blanking via xset (run as the GUI user)
if command -v xset >/dev/null 2>&1; then
  echo "Disabling screen blanking via xset (as ${USER})" >> "$LOG"
  su - "${USER}" -c "DISPLAY=${DISPLAY} XAUTHORITY=${XAUTH} xset s off" >> "$LOG" 2>&1 || true
  su - "${USER}" -c "DISPLAY=${DISPLAY} XAUTHORITY=${XAUTH} xset -dpms" >> "$LOG" 2>&1 || true
  su - "${USER}" -c "DISPLAY=${DISPLAY} XAUTHORITY=${XAUTH} xset s noblank" >> "$LOG" 2>&1 || true
fi

# Copy motorData if present (your original behavior)
SOURCE="/home/orangepi/Code/gigi/Character/motorData_calibrated_local.json"
DEST="/home/orangepi/Code/gigi/Character/motorData_calibrated.json"
if [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$DEST"
    echo "[$(date)] File copied to $DEST" >> "$LOG"
else
    echo "[$(date)] Source file does not exist: $SOURCE" >> "$LOG"
fi

# Wait for the specific USB audio device to appear in `aplay -l`
echo "Waiting for USB speaker (up to ${MAX_WAIT_USB}s)..." >> "$LOG"
j=0
found_usb=0
APLAY_OUT=""
while [ $j -lt $MAX_WAIT_USB ]; do
  APLAY_OUT=$(aplay -l 2>/dev/null || true)
  for pat in "${USB_DEVICE_PATTERNS[@]}"; do
    printf '%s\n' "${APLAY_OUT}" | grep -F -q "${pat}" && { found_usb=1; echo "Detected USB audio by pattern '${pat}'" >> "$LOG"; break; }
  done
  [ "${found_usb}" -eq 1 ] && break
  sleep 1
  j=$((j+1))
done

if [ "${found_usb}" -ne 1 ]; then
  echo "Timeout waiting for USB speaker after ${MAX_WAIT_USB}s. aplay -l output:" >> "$LOG"
  aplay -l >> "$LOG" 2>&1 || true
  echo "Proceeding without detected USB speaker; script may fall back." >> "$LOG"
else
  echo "aplay -l (matching snippet):" >> "$LOG"
  printf '%s\n' "${APLAY_OUT}" | grep -F -E "$(printf '%s|' "${USB_DEVICE_PATTERNS[@]}" | sed 's/|$//')" >> "$LOG" 2>&1 || true
fi

# As a convenience, allow local user access to the X server (safe: localuser only)
if command -v xhost >/dev/null 2>&1; then
  echo "Running xhost +SI:localuser:${USER} (as ${USER})" >> "$LOG"
  su - "${USER}" -c "DISPLAY=${DISPLAY} XAUTHORITY=${XAUTH} xhost +SI:localuser:${USER}" >> "$LOG" 2>&1 || true
fi

# Finally start the Python script as the desktop user, with env set
echo "Starting python script as ${USER} at $(date) (found_usb=${found_usb})" >> "$LOG"
# Use exec so PID is replaced by python (cron job will not keep running otherwise)
exec su - "${USER}" -c "DISPLAY=${DISPLAY} XAUTHORITY=${XAUTH} ${PYTHON} ${SCRIPT}" >> "$LOG" 2>&1