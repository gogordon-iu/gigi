"""
Calibration utilities and profile loader for Gigi robot hardware.
Handles servo limits, neutral positions, and gaze/lookat mapping.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from gigi.core.config import PROJECT_ROOT, DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_MOTOR_MAP: Dict[str, Dict[str, Any]] = {
    "neck": {
        "channel": 1,
        "min": 200,
        "max": 350,
        "center": 275,
        "calibrated": True,
        "direction": "left",
    },
    "torso": {
        "channel": 0,
        "min": 200,
        "max": 400,
        "center": 300,
        "calibrated": True,
        "direction": "left",
    },
    "left_shoulder": {
        "channel": 3,
        "min": 200,
        "max": 400,
        "center": 325,
        "calibrated": True,
        "direction": "down",
    },
    "right_shoulder": {
        "channel": 2,
        "min": 75,
        "max": 300,
        "center": 150,
        "calibrated": True,
        "direction": "up",
    },
    "left_elbow": {
        "channel": 14,
        "min": 275,
        "max": 325,
        "center": 300,
        "calibrated": True,
        "direction": "in",
    },
    "right_elbow": {
        "channel": 15,
        "min": 325,
        "max": 375,
        "center": 350,
        "calibrated": True,
        "direction": "out",
    },
}


def get_motor_calibration_paths():
    """Returns candidate paths for motor calibration data in order of priority."""
    return [
        PROJECT_ROOT / "motorData_calibrated_local.json",
        PROJECT_ROOT / "motorData_calibrated.json",
        PROJECT_ROOT / "motorData.json",
        PROJECT_ROOT / "Character" / "motorData_calibrated.json",
        PROJECT_ROOT / "Character" / "motorData.json",
    ]


def load_motor_calibration() -> Dict[str, Dict[str, Any]]:
    """Loads motor calibration parameters from disk, falling back to safe defaults."""
    for path in get_motor_calibration_paths():
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded motor calibration from {path}")
                return data
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")

    logger.info("Using built-in default motor calibration profile.")
    return DEFAULT_MOTOR_MAP.copy()


def save_motor_calibration(data: Dict[str, Dict[str, Any]], custom_path: Optional[Path] = None) -> Path:
    """Saves motor calibration profile to disk."""
    target_path = custom_path or (PROJECT_ROOT / "motorData_calibrated.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    logger.info(f"Saved motor calibration to {target_path}")
    return target_path


def load_lookat_calibration() -> Dict[str, Any]:
    """Loads lookat gaze calibration interpolation points."""
    candidate_paths = [
        PROJECT_ROOT / "lookat_calibrated.json",
        PROJECT_ROOT / "Character" / "lookat_calibrated.json",
    ]
    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
    return {}
