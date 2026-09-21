#!/usr/bin/env bash
# ==============================================================================
# Gigi Robot Platform - Orange Pi / Ubuntu Linux System Provisioning Script
# ==============================================================================
set -e

# Target user for group permissions (defaults to SUDO_USER if run via sudo, or current user)
TARGET_USER="${SUDO_USER:-$USER}"

echo "============================================================"
echo "          Gigi Robot Platform Provisioning Setup            "
echo "============================================================"
echo "Target User: $TARGET_USER"

# 1. Update and install core system dependencies
echo "[*] Installing system dependencies..."
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  wget \
  ca-certificates \
  tar \
  pocketsphinx \
  python3-pocketsphinx \
  portaudio19-dev \
  espeak \
  cmake \
  i2c-tools \
  gpiod \
  libgpiod-dev \
  mpv \
  wmctrl \
  xdotool \
  unclutter \
  bluez \
  bluez-tools

# 2. Configure GPIO and I2C group permissions
echo "[*] Configuring device group permissions for '$TARGET_USER'..."
sudo groupadd -f gpio
sudo groupadd -f i2c

if [ -e /dev/gpiochip0 ]; then
  sudo chown root:gpio /dev/gpiochip0 || true
  sudo chmod 660 /dev/gpiochip0 || true
fi

# Add target user to hardware access groups
sudo usermod -aG gpio "$TARGET_USER" || true
sudo usermod -aG i2c "$TARGET_USER" || true

# 3. Locate Project Directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

echo "[*] Project root detected at: $PROJECT_ROOT"

# 4. Set up Python Virtual Environment
VENV_DIR="$PROJECT_ROOT/venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "[*] Creating Python virtual environment at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

echo "[*] Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "[*] Upgrading pip and installing dependencies..."
pip install --upgrade pip
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
  pip install -e "$PROJECT_ROOT"
fi

# CPU-only PyTorch for resource-constrained SBCs
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || true

# 5. Set speaker volume if hardware ALSA device exists
echo "[*] Adjusting default PCM audio level..."
amixer -c 2 set PCM 80% 2>/dev/null || amixer set Master 80% 2>/dev/null || true

echo "============================================================"
echo " SUCCESS: System dependencies and Python venv configured!   "
echo " Note: Log out and log back in for group changes to take    "
echo " effect (gpio/i2c permissions).                            "
echo "============================================================"
