# Gigi Robot Platform - Orange Pi 5 & Linux Provisioning Guide

This guide covers the initial hardware setup, operating system configuration, dependency installation, NPU acceleration, and system service management for running **Gigi** on an **Orange Pi 5 / 5 Pro** (Rockchip RK3588 / RK3588S) or standard Debian/Ubuntu Linux single-board computer.

---

## 1. Operating System & Kernel Overlays

### 1.1 Enable I2C Bus for Servo Motors
The PCA9685 PWM servo driver communicates over an I2C bus. On Rockchip systems running Ubuntu or Armbian:

1. Edit `/boot/orangepiEnv.txt`:
   ```bash
   sudo nano /boot/orangepiEnv.txt
   ```
2. Ensure the appropriate I2C overlay is active:
   - For **Orange Pi 5 / 5B** (RK3588S):
     ```ini
     overlays=i2c2-m1
     ```
   - For **Orange Pi 5 Pro** (using I2C-5):
     ```ini
     overlays=i2c5-m3
     ```
3. Reboot the system:
   ```bash
   sudo reboot
   ```
4. Verify the I2C bus appears:
   ```bash
   i2cdetect -y 2   # or 5 depending on the active overlay
   ```

---

## 2. System Dependencies & User Permissions

Run the automated setup script to install system libraries, create the Python virtual environment, and configure device permissions:

```bash
cd ~/Code/gigi/Setup
chmod +x setup_orangepi.sh
./setup_orangepi.sh
```

This script installs:
- **Core build tools & audio**: `python3-venv`, `portaudio19-dev`, `pocketsphinx`, `espeak`, `cmake`
- **Motor control & GPIO**: `i2c-tools`, `gpiod`, `libgpiod-dev`
- **Kiosk & display tools**: `mpv`, `wmctrl`, `xdotool`, `unclutter`
- **User group permissions**: Adds the active user to the `i2c` and `gpio` groups so robot control does not require `sudo`.

---

## 3. Display Kiosk Mode (Disabling Screen Blanking)

To keep Gigi's expressive face on the screen at all times without sleep timeouts:

1. **Disable GNOME/Desktop Idle Delay & Lock**:
   ```bash
   gsettings set org.gnome.desktop.session idle-delay 0
   gsettings set org.gnome.desktop.screensaver lock-enabled false
   ```

2. **Disable X11 DPMS & Screen Blanking**:
   ```bash
   xset s off
   xset s noblank
   xset -dpms
   ```

3. **Make Permanent**: Add the X11 settings to your shell profile (`~/.bashrc` or `~/.xprofile`):
   ```bash
   echo "xset s off && xset s noblank && xset -dpms" >> ~/.xprofile
   ```

4. **Kiosk Update Popups**:
   To prevent Ubuntu release upgrade or update-notifier windows from obscuring Gigi's face:
   ```bash
   sudo Setup/close_update_popup.sh --disable-services
   ```

---

## 4. Bluetooth Hub & Headless Pairing

Gigi communicates with the tablet app (`gigi-mobile-app`) over Bluetooth RFCOMM (Serial Port Profile).

### 4.1 BlueZ Compatibility Mode
BlueZ must run with the compatibility flag (`-C` or `--compat`) to register the SPP profile:
```bash
sudo Setup/fix_bluetooth_compat.sh
```

### 4.2 Auto-Pairing Agent (`bt_agent.py`)
Gigi includes a headless auto-pairing agent that automatically accepts pairing requests from authorized tablets:
- Default PIN: `198420` (matching the default in the companion app)
- Can be overridden via environment variable:
  ```bash
  export GIGI_BT_PIN="<your_secure_pin>"
  ```

### 4.3 Automated Systemd Service
To launch the Bluetooth listener and auto-pairing agent automatically on system boot and resume from sleep:
```bash
sudo Setup/setup_bluetooth_startup.sh
```
Check status:
```bash
sudo systemctl status gigi-bluetooth.service
```

---

## 5. On-Device NPU Acceleration (Rockchip RK3588)

Gigi utilizes the 6-TOPS Rockchip NPU for fast, local LLM inference and speech recognition.

### 5.1 NPU LLM Compilation (Qwen / RKLLM)
To convert a Hugging Face language model (e.g., Qwen) to `.rkllm` format for the Orange Pi:
1. On an x86 Linux machine with 16GB+ RAM and Python 3.10+:
   ```bash
   git clone https://github.com/airockchip/rknn-llm.git
   cd rknn-llm/rkllm-toolkit/packages
   pip install rkllm_toolkit-*.whl
   ```
2. Build the model with quantization:
   ```python
   from rkllm.api import RKLLM

   llm = RKLLM()
   llm.load_huggingface(model="Qwen/Qwen2.5-0.5B-Instruct")
   llm.build(do_quantization=True, optimization_level=1, quantized_dtype="w8a8", target_platform="rk3588")
   llm.export_rkllm("qwen-0.5b-rk3588.rkllm")
   ```
3. Copy the `.rkllm` model to Gigi's `Resources/` directory on the Orange Pi.
4. Set NPU performance governors:
   ```bash
   sudo bash Resources/rknn-llm/examples/rkllm_server_demo/rkllm_server/fix_freq_rk3588.sh
   ```

### 5.2 Speech Recognition (SenseVoice RKNN2)
1. On the Orange Pi:
   ```bash
   pip install kaldi_native_fbank sentencepiece soundfile pyyaml "numpy<2"
   pip install rknn_toolkit_lite2-*.whl
   ```
2. Place the converted models in `Resources/`:
   - `Resources/sense-voice-encoder.rknn`
   - `Resources/chn_jpn_yue_eng_ko_spectok.bpe.model`

---

## 6. Autostart on Boot

To start Gigi automatically on robot power-up:

1. Edit the user crontab:
   ```bash
   crontab -e
   ```
2. Add the following entry:
   ```cron
   SHELL=/bin/bash
   PATH=/home/<username>/Code/gigi/venv/bin:/usr/local/bin:/usr/bin:/bin
   DISPLAY=:0
   @reboot /home/<username>/Code/gigi/Setup/wakeup_gigi.sh >> /home/<username>/Code/gigi/Logs/wakeup.log 2>&1
   ```

---

## 7. Diagnostics & Maintenance

- **Bluetooth Diagnostics**: Run `python3 Setup/bt_diagnostic.py` to inspect BlueZ daemon flags, active RFCOMM devices, and local SDP registrations.
- **Process Management**: Use `Setup/kill_wakeup.sh` to safely stop running background robot instances during development.
