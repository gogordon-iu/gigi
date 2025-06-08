#!/bin/bash

export DISPLAY=:0
export XAUTHORITY=/home/orangepi/.Xauthority

# Prevent screen blanking
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
chmod +x activate_environment.sh
./activate_environment.sh
source venv/bin/activate
cd Character
python wakeUp.py        # exec keeps service alive
