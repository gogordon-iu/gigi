#!/usr/bin/env bash
# ==============================================================================
# Gigi Robot Platform - System Wakeup / Startup Script
# ==============================================================================

# Locate project root dynamically relative to script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

export DISPLAY=:0
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# Prevent screen blanking and kiosk sleep
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null || true
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null || true

xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset s noblank 2>/dev/null || true

# Copy local calibrated motor configuration if present
SOURCE="$PROJECT_ROOT/motorData_calibrated_local.json"
DEST="$PROJECT_ROOT/motorData_calibrated.json"

if [ -f "$SOURCE" ]; then
    cp "$SOURCE" "$DEST"
    echo "[Wakeup] Applied local motor calibration from $SOURCE"
fi

cd "$PROJECT_ROOT"

# Activate Python Virtual Environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

if [ -f "activate_environment.sh" ]; then
    source activate_environment.sh
fi

exec python3 -m gigi.core.daemon
