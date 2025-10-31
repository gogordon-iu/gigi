#!/bin/bash

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
