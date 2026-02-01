#!/bin/bash

XAUTH=/home/orangepi/.Xauthority
DISPLAY_NUM=":0"
MAX_WAIT=60   # seconds to wait for X to appear

# Wait for X server (socket / process) or for Xauthority file to exist
i=0
while [ $i -lt $MAX_WAIT ]; do
  # check for Xorg process or socket
  if pgrep -x Xorg >/dev/null 2>&1 || [ -f "$XAUTH" ]; then
    break
  fi
  sleep 1
  i=$((i+1))
done

if [ $i -ge $MAX_WAIT ]; then
  echo "Timeout waiting for X after ${MAX_WAIT}s"
  exit 1
fi

export DISPLAY=:0
export XAUTHORITY=/home/orangepi/.Xauthority

# Prevent screen blanking

gsettings set org.gnome.desktop.session idle-delay 0
gsettings set org.gnome.desktop.screensaver lock-enabled false

echo "xset s off && xset s noblank && xset -dpms" >> ~/.bashrc

xset s off
xset -dpms
xset s noblank

SOURCE="/home/orangepi/Code/gigi/Character/motorData_calibrated_local.json"
DEST="/home/orangepi/Code/gigi/Character/motorData_calibrated.json"

if [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$DEST"
    echo "File copied to $DEST"
else
    echo "Source file does not exist: $SOURCE"
fi


cd /home/orangepi/Code/gigi
source venv/bin/activate
source activate_environment.sh

cd Character
python wakeUp.py        # exec keeps service alive
