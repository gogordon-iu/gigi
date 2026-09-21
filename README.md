# Gigi: Open-Source Social Robot Platform

[![CI](https://github.com/gogordon-iu/gigi/actions/workflows/ci.yml/badge.svg)](https://github.com/gogordon-iu/gigi/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Hardware: Orange Pi 5 Pro](https://img.shields.io/badge/Hardware-Orange_Pi_5_Pro-orange.svg)](http://www.orangepi.org/)
[![Platform: Linux / Windows / macOS](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)]()
[![Git LFS](https://img.shields.io/badge/Git%20LFS-Enabled-blueviolet.svg)](https://git-lfs.github.com)
[![Mobile App](https://img.shields.io/badge/Mobile%20App-gigi--app-61DAFB.svg)](https://github.com/gogordon-iu/gigi-app)

**Gigi** is an open-source, expressive desktop social robot platform designed for Human-Robot Interaction (HRI), educational tutoring, developmental cognitive studies, and autonomous social presence. 

Powered by an onboard **Orange Pi 5 Pro** (Rockchip RK3588S SoC with 8-core CPU and 6 TOPS NPU) and a high-resolution portrait display, Gigi features animated facial expressions, viseme-accurate lip synchrony, multiaxis servo body gestures, real-time computer vision with gaze tracking, acoustic speaker identification, and adaptive LLM-driven pedagogical interactions.

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Repository & Package Layout](#repository--package-layout)
3. [Subsystem Deep Dive](#subsystem-deep-dive)
4. [Hardware Abstraction & Simulation](#hardware-abstraction--simulation)
5. [Getting Started (Local Workstation)](#getting-started-local-workstation)
6. [Git LFS Setup for Neural Weights](#git-lfs-setup-for-neural-weights)
7. [Motor Calibration & Physical Safety Lockout](#motor-calibration--physical-safety-lockout)
8. [Interactive Live Demonstration](#interactive-live-demonstration)
9. [Running Subsystem Tests](#running-subsystem-tests)
10. [CLI Usage Guide](#cli-usage-guide)
11. [Deploying to Physical Robot (Orange Pi 5 Pro)](#deploying-to-physical-robot-orange-pi-5-pro)
12. [Mobile & Web Companion App](#mobile--web-companion-app)
13. [Community, Contributing & Security](#community-contributing--security)
14. [Historical Code Archive](#historical-code-archive)
15. [License & Citation](#license--citation)

---

## System Architecture Overview

Gigi's software stack is organized into clean, modular layers following clean architecture principles:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ACTIVITIES & APPLICATIONS                          │
│   Reading Fluency  •  Mastermind  •  Story Game  •  Math Quest  •  Alive │
├─────────────────────────────────────────────────────────────────────────┤
│                   INTERACTION & COGNITIVE PLANNING                      │
│   Interaction Manager  •  Strategy Catalog  •  Safety Filter  •  LLM    │
├───────────────────────────────────┬─────────────────────────────────────┤
│         PERCEPTION LAYER          │          EXPRESSION LAYER           │
│  • Vision (Face / Gaze / Emotion) │  • Animated Face Display (Pygame/CV)│
│  • Hearing (Whisper / Vosk ASR)   │  • Speech Synthesis (Silero / Piper)│
│  • Speaker ID (Resemblyzer/RKNN)  │  • Viseme Lip-Sync Generation       │
│  • Pronunciation Evaluation (GOP) │  • Kinematic Servo Gestures (S-Curve│
├───────────────────────────────────┴─────────────────────────────────────┤
│                     CORE ORCHESTRATION & DAEMON                         │
│       GigiRobot Manager  •  Interaction Logger  •  Bluetooth / TCP      │
├─────────────────────────────────────────────────────────────────────────┤
│                     HARDWARE ABSTRACTION LAYER (HAL)                    │
│   PCA9685 Servos (Real / Sim) • Camera (V4L2/DShow) • RK3588 NPU Runner │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Repository & Package Layout

The repository follows standard Python packaging (`src/` layout) governed by `pyproject.toml` (PEP 621):

```
gigi/
├── Assets/                        # Character graphics, UI feedback icons, audio recordings
│   ├── face/                      # Sprite sheets for characters: fuzzy, gigi, tutti, valera
│   ├── audio/                     # Sound effects and activity prompt audio
│   └── recorded_speech/           # Local cache of synthesized speech waveforms
├── Resources/                     # Acoustic models, neural weights, and NPU binaries
│   ├── vosk-model-small-en-us/    # Offline Kaldi/Vosk speech recognition models
│   ├── voice-encoder.rknn         # Precompiled RKNN NPU model for speaker identification
│   └── nix/                       # Nix TTS model files
├── Setup/                         # Linux & Orange Pi provisioning scripts and services
│   ├── systemd/                   # systemd unit files (gigi.service, bluetooth daemon)
│   ├── udev/                      # udev rules for serial ports and I2C permissions
│   └── scripts/                   # Shell scripts for hardware initialization on boot
├── tests/                         # Automated unit & subsystem test suite (31 tests)
│   ├── test_local_subsystems.py   # Tests core, HAL, perception, expression, CLI
│   └── test_activity_logic.py     # Tests Mastermind, Math Quest, Story Game, Script Graphs
├── tools/
│   ├── interactive_session.py     # Live interactive camera, face, mic & speech runner
│   └── deploy.py                  # SSH & Rsync deployment tool for physical Orange Pi
├── src/
│   └── gigi/                      # The root importable Python package
│       ├── core/                  # Core orchestration & lifecycle management
│       ├── hardware/              # Hardware Abstraction Layer (HAL) & simulation
│       ├── perception/            # Computer vision, hearing, speaker recognition
│       ├── expression/            # Screen rendering, speech synthesis, gestures
│       ├── interaction/           # Educational planning, turn-taking, safety, LLM
│       ├── activities/            # Integrated educational games and social behaviors
│       ├── verification/          # Standalone verification & diagnostic subsystem
│       └── cli.py                 # Unified command-line interface entry point (`gigi`)
├── motorData.json                 # Hardware motor pin assignments and channel mapping
├── motorData_calibrated.json      # Servo limits, neutral offsets, and gaze calibration
├── pyproject.toml                 # Modern PEP 621 package metadata & CLI entry points
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git ignore rules (protects credentials & biometrics)
└── README.md                      # This documentation file
```

---

## Subsystem Deep Dive

### 1. Core (`gigi.core`)
- **`robot.py`**: The `GigiRobot` (and alias `Character`) class orchestrates all subsystems. It manages the lifecycle of perception, expression, conversation, and logging.
- **`config.py`**: Centralized, typed configuration. Automatically resolves absolute project paths (`ASSETS_DIR`, `RESOURCES_DIR`) and detects runtime environment (`IS_ROBOT = True` on Linux / Orange Pi; `False` on Windows/macOS).
- **`logger.py`**: Structured interaction logging (`InteractionLogger`). Records time-synchronized audio streams, video frames, transcribed text, robot actions, and user feedback into user-specific session folders.
- **`daemon.py`**: Dual-protocol communication server supporting Bluetooth RFCOMM (for the Gigi mobile tablet app) and TCP sockets (for desktop orchestration).
- **`conversation.py`**: Multi-turn dialogue management, intent recognition, and short-term conversational context.

### 2. Hardware Abstraction Layer (`gigi.hardware`)
- **`motors.py`**: PCA9685 I2C 16-channel PWM servo controller. Detects physical I2C bus availability. On workstations (Windows/macOS), it **automatically defaults to software simulation mode**, allowing full kinematic calculations without crashing.
- **`calibration.py`**: Reads, verifies, and persists servo limits (`min_pulse`, `max_pulse`), neutral positions, and look-at orientation parameters from `motorData_calibrated.json`.
- **`camera.py`**: Video capture port enumeration and initialization with DirectShow (Windows) or V4L2 (Linux) backend selection.
- **`npu.py`**: Interface to Rockchip's `rknnlite` runtime for running accelerated ONNX-to-RKNN models on the RK3588 NPU.

### 3. Perception (`gigi.perception`)
- **`vision.py` & `vision_helper.py`**: Real-time face detection, facial landmark mesh tracking, head pose / eye gaze estimation, and facial emotion classification using MediaPipe and OpenCV.
- **`hearing.py` & `whisper_helper.py`**: Streaming ASR using **Faster-Whisper** (`int8` quantization) and offline **Vosk**. Includes WebRTC Voice Activity Detection (VAD), dynamic ambient noise calibration, and linear audio resampling (48 kHz mic to 16 kHz model).
- **`speaker_id.py`**: Voice embedding database matching user vocal prints for speaker verification.
- **`pronunciation.py`**: Goodness of Pronunciation (GOP) phoneme scoring using Citrinet acoustic models.

### 4. Expression (`gigi.expression`)
- **`face_display.py` & `face_definitions.py`**: 2D animated face engine with character profiles (`fuzzy`, `gigi`, `tutti`). Renders dynamic blinking, gaze redirection, smiling, speaking mouth shapes, and visual feedback icons (such as the **listening ear** indicator). Supports both Pygame and OpenCV rendering backends in windowed or fullscreen modes.
- **`speech.py`**: Multimodal speech synthesis supporting **Silero TTS**, **Piper**, **MeloTTS**, and **eSpeak-NG**, with automatic local waveform caching.
- **`visemes.py`**: Synchronizes facial mouth visemes with speech waveform envelopes for realistic lip movements.
- **`movement.py` & `gesture_definitions.py`**: Generates smooth multiaxis kinematic trajectories using S-curve interpolation across 6 degrees of freedom (neck, torso, left/right shoulder, left/right elbow).

### 5. Interaction Engine (`gigi.interaction`)
*(Integrated from the legacy `Zhennan/` activity controller)*
- **`planner.py`**: Curriculum and pedagogical activity planner.
- **`manager.py`**: Turn-taking interaction manager mediating conversational flow between child and robot.
- **`strategies.py`**: Catalog of pedagogical and social strategies (encouragement, scaffolding, self-disclosure, hints).
- **`safety_filter.py`**: Safety filter inspecting LLM outputs and user inputs for age-appropriate language.
- **`llm/`**: Pluggable multi-provider client supporting local **Ollama** models, OpenAI API, and Azure OpenAI.
- **`web/`**: Lightweight Flask web application providing a graphical user interface for designing interaction plans and previewing pedagogical strategies.

### 6. Activities (`gigi.activities`)
*(Integrated from legacy `Demo/` and `Scripts/`)*
- **`reading_fluency/`**: Interactive reading fluency tutor with karaoke-style word highlighting and phoneme pronunciation assistance.
- **`mastermind/`**: Color and number logic codebreaker game with automated deduction solvers.
- **`story_game/`**: Vision-based interactive scavenger and story game where children present real-world objects to the camera.
- **`math_quest/`**: Mental arithmetic challenge with spoken question generation and speech-parsed numeric answers.
- **`alive_mode/`**: Autonomous social presence behavior with natural gaze shifts, blinking, face tracking, and subtle breathing gestures.
- **`scripted/`**: Directed graph activity engine (`ScriptGraph`) running reproducible lessons (`Ferris Wheel`, `Bilingual Lego`, `Halloween`).

### 7. Verification (`gigi.verification`)
*(Standalone package)*
- **`hardware/`**: Diagnostics for physical actuators: `verify_motors`, `verify_camera`, `verify_screen`, `verify_mic`, `verify_speaker`, `verify_gestures`, `calibrate_motors`.
- **`ai/`**: Cognitive pipeline diagnostics: `verify_stt`, `verify_tts`, `verify_face`, `verify_follow_face`, `verify_voice`, `verify_llm`.
- **`cli.py`**: Diagnostic test dispatcher invoked via `gigi verify` or `gigi-verify`.

---

## Hardware Abstraction & Simulation

Gigi is built to be developed, tested, and demonstrated on **any personal computer (Windows, macOS, Linux)** without requiring the physical robot:

| Subsystem | On Physical Robot (Orange Pi 5 Pro) | On Host Workstation (Windows / macOS) |
| :--- | :--- | :--- |
| **Servos (PCA9685)** | Hardware I2C bus (`/dev/i2c-3`) | Software simulation mode (kinematics verified, no hardware errors) |
| **Camera** | V4L2 USB camera (`/dev/video0`) | DirectShow / OpenCV webcam (`cv2.VideoCapture(0)`) |
| **Display** | Fullscreen portrait LCD (800×1280) | Resizable desktop window (Pygame / OpenCV) |
| **Microphone** | ReSpeaker / USB mic array | Default OS audio input (built-in mic, headset, USB mic) |
| **Speakers** | 3.5mm / USB amplifier audio output | Default OS audio output (speakers / headphones) |
| **NPU Acceleration**| Rockchip RK3588 6 TOPS NPU (`rknnlite`) | CPU fallback via PyTorch, ONNXRuntime, and Faster-Whisper |

---

## Getting Started (Local Workstation)

### 1. Prerequisites
- **Python 3.10, 3.11, or 3.12**
- Git
- A working webcam, microphone, and speakers

### 2. Setup Virtual Environment
```powershell
# Clone the repository
git clone https://github.com/gogordon-iu/gigi.git
cd gigi

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install Gigi in editable development mode
pip install -e .
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
*(Optional: set your `OPENAI_API_KEY` or configure local `OLLAMA_BASE_URL` in `.env` if using LLM features).*

---

## Git LFS Setup for Neural Weights

Gigi utilizes pre-trained acoustic models, neural viseme mapping tables, and embedded RKNN NPU binaries. These binary assets are managed under **Git Large File Storage (LFS)**:

```bash
# Install Git LFS hooks on your machine
git lfs install

# Pull all model weights and binary assets
git lfs pull
```

The tracked binary patterns include `*.onnx`, `*.rknn`, `*.mdl`, `*.fst`, `*.dubm`, `*.ie`, `*.mat`, `*.pt`, and `*.pth`.

---

## Motor Calibration & Physical Safety Lockout

Physical safety of child participants and prevention of servo gear damage are paramount in social robotics.

### Calibration Safety Architecture
- **Robot-Specific Calibrations**: Servo horn alignments, physical offsets, and mechanical linkage limits vary from unit to unit. The active calibration is stored locally in `motorData_calibrated.json` and is strictly **excluded from Git**.
- **Template Reference**: Newly flashed robots or fresh checkouts receive `motorData_calibrated.example.json` containing default center points and safe travel bounds.
- **Hardware Lockout Guard**: When the robot powers on or starts the background daemon, the system verifies whether `motorData_calibrated.json` exists and differs from the uncalibrated template.
  - If **uncalibrated**, all physical servo movements (gestures, arm swings, neck tilts) are **locked out**. Any attempt to command physical movement returns a safety error: `{"status": "error", "error": "uncalibrated", "requires_calibration": true}`.
  - Speech, facial animation, and cognitive reasoning remain fully operational.

### Running the Motor Calibration Wizard
To calibrate a physical robot:
```bash
# Run locally on the robot via CLI
gigi calibrate
```
Or trigger calibration remotely from the **Gigi Mobile App** or Bluetooth terminal by sending:
```
CALIBRATE
```
Once the calibration sequence successfully completes, `motorData_calibrated.json` is updated and the hardware lockout is immediately lifted.

---

## Interactive Live Demonstration

Experience Gigi's multimodal loop in real time right on your computer screen:

```powershell
python tools/interactive_session.py
```

### What this runs:
1. **Gigi Animated Face Window**: Opens Gigi's 2D animated face on your desktop, with blinking, smiling, and looking around.
2. **Real-Time Camera Feed Window**: Captures your webcam feed with real-time face detection (`"User Detected"`).
3. **Speech Synthesis (TTS)**: Gigi introduces herself out loud through your computer speakers.
4. **Speech Recognition (ASR)**: The visual **listening ear icon** illuminates on Gigi's face. Gigi records your voice from your microphone, transcribes it with Faster-Whisper, prints it to the console, and speaks back what it heard!

---

## Running Subsystem Tests

Run the complete 31-test automated suite across core configs, hardware simulation, perception algorithms, game logic, and script graphs:

```powershell
# Run full unit test suite
python -m unittest discover -s tests -p "test_*.py" -v
```

All 31 tests run locally in simulation without physical robot hardware.

---

## CLI Usage Guide

The unified `gigi` command-line tool provides intuitive subcommands:

```powershell
# View all available commands
gigi --help

# 1. Run hardware and cognitive diagnostics
gigi verify all
gigi verify camera
gigi verify motors
gigi verify screen
gigi verify speaker
gigi verify mic
gigi verify face
gigi verify llm

# 2. Launch the Web Activity Planner (visual curriculum builder)
gigi web --port 5000
# Open http://localhost:5000 in your browser

# 3. Launch interactive robot capabilities demo
gigi demo

# 4. Calibrate robot servo limits (when connected to physical robot)
gigi calibrate

# 5. Start background daemon (Bluetooth RFCOMM + TCP server)
gigi start
```

---

## Deploying to Physical Robot (Orange Pi 5 Pro)

When you are ready to synchronize your code updates to the physical Gigi robot over Wi-Fi/Ethernet:

```powershell
# Synchronize code to robot over SSH / Rsync
python tools/deploy.py --host 192.168.0.50

# Deploy and automatically restart the background systemd service
python tools/deploy.py --host 192.168.0.50 --restart-service
```

Deployment excludes local virtual environments (`venv/`), caches (`__pycache__`), and sensitive environment files while ensuring the robot receives the clean `src/` packages.

---

## Mobile & Web Companion App

The **Gigi Classroom Assistant Portal** (`gigi-app`) is the official React Native / Web application for classroom teachers, students, and researchers:
- **Repository**: [`gogordon-iu/gigi-app`](https://github.com/gogordon-iu/gigi-app)
- **Features**: Direct Web Serial Bluetooth connection, real-time log monitoring, one-touch activity launching, AI Lesson Planner with Azure OpenAI GPT-4o, automated DALL-E 3 image generation, and dynamic state-machine authoring.

---

## Community, Contributing & Security

We welcome contributions, feature suggestions, and research collaborations!
- **Contributing Guidelines**: See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup and pull request workflows.
- **Code of Conduct**: We adhere to the Contributor Covenant v2.1. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- **Security Policy**: For vulnerability reporting and physical robot safety disclosures, refer to [SECURITY.md](SECURITY.md).

---

## Historical Code Archive

In accordance with our code cleaning and public release policy:
- The full, unedited historical codebase and previous commit history have been preserved and archived at:  
  **[`gogordon-iu/gigi-archive`](https://github.com/gogordon-iu/gigi-archive.git)**
- The current repository represents the clean, restructured, and tested architecture intended for public open-source distribution and Orange Pi 5 Pro eMMC flashing.

---

## License & Citation

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

Developed by the **Human-Robot Interaction & Social Robotics Team** at **Indiana University Bloomington**.
