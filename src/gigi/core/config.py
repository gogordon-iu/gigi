"""
Central configuration for Gigi.

Provides runtime detection (robot vs host PC), path resolution,
feature toggles, and motor/vision tracking constants.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

# Resolve the root directory of the repository (parent of src/)
CORE_DIR = Path(__file__).resolve().parent
GIGI_PKG_DIR = CORE_DIR.parent
SRC_DIR = GIGI_PKG_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

# Standard directory paths
ASSETS_DIR = PROJECT_ROOT / "Assets"
RESOURCES_DIR = PROJECT_ROOT / "Resources"
SETUP_DIR = PROJECT_ROOT / "Setup"
DATA_DIR = PROJECT_ROOT / "data"
CHARACTER_FOLDER = str(PROJECT_ROOT / "Character") + "/"
base_assets_path = str(ASSETS_DIR) + "/"


# Runtime detection: Check OS or environment variable override
_env_is_robot = os.environ.get("GIGI_IS_ROBOT")
if _env_is_robot is not None:
    IS_ROBOT = _env_is_robot.lower() in ("true", "1", "yes")
else:
    IS_ROBOT = sys.platform.startswith("linux")

# Hardware acceleration flags (Orange Pi 5 Pro / RK3588 NPU)
USE_NPU_TRANSCRIPTION: bool = os.environ.get("GIGI_USE_NPU_TRANSCRIPTION", str(IS_ROBOT)).lower() in ("true", "1", "yes")
USE_NPU_SPEAKER: bool = os.environ.get("GIGI_USE_NPU_SPEAKER", "false").lower() in ("true", "1", "yes")
USE_NPU_PRONUNCIATION: bool = os.environ.get("GIGI_USE_NPU_PRONUNCIATION", str(IS_ROBOT)).lower() in ("true", "1", "yes")

# Subsystem feature toggles
HAS_FACE: bool = True
HAS_SPEECH: bool = True
HAS_VISEME: bool = True
HAS_HEARING: bool = True
HAS_VISION: bool = True
HAS_MOVEMENT: bool = IS_ROBOT
HAS_CONVERSATION: bool = True

# Daemon & networking settings
DEFAULT_ROBOT_IP = os.environ.get("ROBOT_IP", "127.0.0.1")
DEFAULT_TCP_PORT = int(os.environ.get("TCP_PORT", "5005"))
DEFAULT_RFCOMM_CHANNEL = int(os.environ.get("RFCOMM_CHANNEL", "1"))

# Vision & Face tracking thresholds
FOLLOW_TORSO_OFFSET: float = 0.5
FOLLOW_NECK_OFFSET: float = 0.25
FOLLOW_EYES_OFFSET: float = 0.1
OFFSET_TORSO_RATIO: float = 0.3
OFFSET_NECK_RATIO: float = 0.2
TORSO_FOLLOW_DURATION: float = 1.0
NECK_FOLLOW_DURATION: float = 1.0

# Motor I2C Bus & Address (Orange Pi 5 Pro)
SMBUS_INTERFACE: int = 5
PCA9685_ADDRESS: int = 0x40
PWM_FREQUENCY: int = 50
