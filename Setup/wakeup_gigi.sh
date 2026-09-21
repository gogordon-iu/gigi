#!/bin/bash

export DISPLAY=:0
export XAUTHORITY=/home/orangepi/.Xauthority

# Prevent screen blanking

gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true

xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true

SOURCE="/home/orangepi/Code/gigi/motorData_calibrated_local.json"
DEST="/home/orangepi/Code/gigi/motorData_calibrated.json"

if [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$DEST"
    echo "File copied to $DEST"
fi

cd /home/orangepi/Code/gigi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

if [ -f "activate_environment.sh" ]; then
    source activate_environment.sh
fi

exec python3 -m gigi.core.daemon
