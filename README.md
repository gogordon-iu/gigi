# Gigi: Open-Source Social Robot Platform

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-brightgreen.svg)](https://www.python.org/)
[![Hardware: Orange Pi 5 Pro](https://img.shields.io/badge/Hardware-Orange_Pi_5_Pro-orange.svg)](http://www.orangepi.org/)
[![Platform: Linux / macOS / Windows](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

**Gigi** is an open-source, expressive desktop social robot platform developed for Human-Robot Interaction (HRI), educational tutoring, and developmental cognitive studies. Powered by an onboard Orange Pi 5 Pro (Rockchip RK3588 with 6 TOPS NPU) and a high-resolution portrait display, Gigi features animated facial expressions, viseme-accurate lip synchrony, multiaxis servo body gestures, real-time computer vision, acoustic speaker identification, and adaptive LLM-driven pedagogical interactions.

---

## Key Features

- **Integrated Robot Architecture (`gigi.core`)**: High-level robot orchestration (`GigiRobot`), centralized typed configuration, robust interaction logging, and an event daemon supporting RFCOMM Bluetooth and TCP sockets.
- **Hardware Abstraction Layer (`gigi.hardware`)**: PCA9685 I2C servo controller (with automatic software simulation on macOS/Windows), servo calibration management, video capture, and RKNN NPU runtimes.
- **Multimodal Perception (`gigi.perception`)**:
  - *Vision*: MediaPipe face tracking, eye gaze estimation, and OpenCV object detection.
  - *Hearing*: Dual-layer ASR with offline Kaldi/Vosk and local/remote Whisper, Voice Activity Detection (VAD).
  - *Speaker ID*: Hardware-accelerated NPU speaker embeddings via RKNN and Resemblyzer.
  - *Pronunciation*: Citrinet Goodness of Pronunciation (GOP) phoneme-level evaluation.
- **Rich Expression (`gigi.expression`)**:
  - *Animated Faces*: 2D vector characters rendered via Pygame with dynamic blinks, emotional states, and gaze redirection.
  - *Visemes & Speech*: Lip-sync viseme animation coupled with offline and neural TTS backends (eSpeak-NG, Piper, MeloTTS, Edge-TTS).
  - *Gestural Motor Sequences*: Calibrated multiaxis movements (neck, torso, left/right shoulders and elbows).
- **Pedagogical Interaction Engine (`gigi.interaction`)**: Activity planning, student turn-taking, behavior safety filtering, multi-backend LLM client (Ollama, OpenAI, Azure), and a web-based activity builder.
- **Interactive Activities (`gigi.activities`)**:
  - Reading Fluency tutoring with phoneme feedback.
  - Mastermind color & number codebreaker.
  - Object-recognition interactive Story Game.
  - Mental arithmetic Math Quest.
  - Autonomous social "Alive Mode" and classroom greeting / receptionist behaviors.
  - Replayable scripted pedagogical lessons.
- **Hardware & AI Verification Suite (`gigi.verification`)**: Built-in test dispatcher for motor testing, camera checks, screen calibration, mic/speaker verification, and NPU inference testing.

---

## Package Architecture

```
gigi/
├── Assets/                 # Character sprites, audio recordings, activity media
├── Resources/              # AI models (ONNX, RKNN, Vosk acoustics, speaker databases)
├── Setup/                  # Systemd units, udev rules, Orange Pi system configurations
├── tools/
│   └── deploy.py           # Rsync & SSH deployment script for Orange Pi
├── src/
│   └── gigi/
│       ├── core/           # Config, logging, robot class, daemon, conversation
│       ├── hardware/       # PCA9685 servos, calibration, camera, NPU runner
│       ├── perception/     # Vision, hearing, pronunciation (GOP), speaker ID
│       ├── expression/     # Faces, visemes, speech synthesis, movement sequences
│       ├── interaction/    # Activity planner, pedagogical strategies, safety, LLM
│       ├── activities/     # Reading fluency, games, alive mode, scripted engine
│       ├── verification/   # Hardware & AI diagnostic test suites
│       └── cli.py          # Unified CLI entry point (`gigi`)
├── pyproject.toml          # PEP 621 package specification and entrypoints
├── .env.example            # Environment template for keys and hardware settings
└── README.md
```

---

## Quickstart Guide

### 1. Prerequisites

- **Python 3.10+** (Recommended: 3.10 or 3.11)
- For Linux/Orange Pi: `espeak-ng`, `portaudio19-dev`, `libasound2-dev`
- For Windows/macOS: Standard development toolchain (hardware modules run in automatic simulation mode)

### 2. Installation

Clone the repository and install `gigi` in editable mode:

```bash
git clone https://github.com/gogordon-iu/gigi.git
cd gigi

# Create and activate virtual environment
python -m venv venv
# Linux / Orange Pi:
source venv/bin/activate
# Windows:
.\venv\Scripts\Activate.ps1

# Install gigi package with development dependencies
pip install -e .
```

### 3. Configuration

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` to configure your preferred speech engine, OpenAI/Ollama endpoints, or robot deployment targets.

---

## Command Line Interface (CLI)

The `gigi` CLI provides a unified interface for launching activities, running diagnostics, and configuring hardware:

```bash
# Display top-level help
gigi --help
```

### Start the Background Daemon
Runs the RFCOMM Bluetooth and TCP daemon that listens for remote app control and activity triggers:
```bash
gigi start --host 0.0.0.0 --port 5005
```

### Run Subsystem Verification Tests
Test specific hardware components or perception pipelines:
```bash
# Verify all hardware subsystems (motors, camera, display, audio)
gigi verify hardware

# Verify specific subsystems:
gigi verify motors
gigi verify camera
gigi verify screen
gigi verify speaker
gigi verify mic
gigi verify gestures

# Verify AI pipelines (face tracking, STT, TTS, LLM, NPU):
gigi verify ai
gigi verify stt
gigi verify tts
gigi verify llm
```

### Motor & Camera Calibration
```bash
# Interactively calibrate servo limits and neutral positions
gigi calibrate motors

# Inspect camera FOV and alignment
gigi calibrate camera
```

### Launch Interactive Activities
```bash
# Run autonomous "Alive Mode"
gigi demo alive

# Run Reading Fluency Tutor
gigi demo reading

# Run Mastermind Game
gigi demo mastermind

# Run Classroom / Lab Receptionist
gigi demo receptionist

# Run Introduction to Gigi
gigi demo intro
```

### Launch Web Activity Planner
```bash
gigi web --port 5000
```

---

## Physical Robot Deployment (Orange Pi 5 Pro)

To push code updates from your development workstation directly to the physical robot over SSH/Rsync:

```bash
# Deploy to robot at IP 192.168.0.50
python tools/deploy.py --host 192.168.0.50

# Restart the robot daemon service on the robot after deployment
python tools/deploy.py --host 192.168.0.50 --restart-service
```

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Developed by the **Human-Robot Interaction & Social Robotics Team** at **Indiana University Bloomington**.
