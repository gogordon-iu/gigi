"""
Calibration utilities and profile loader for Gigi robot hardware.
Handles servo limits, neutral positions, and gaze/lookat mapping.

motorData_calibrated.json is strictly robot-local and untracked by Git to protect
each physical robot's custom motor calibration during software updates and git pulls.
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from gigi.core.config import PROJECT_ROOT, DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_MOTOR_MAP: Dict[str, Dict[str, Any]] = {
    "system_calibrated": True,
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
    """
    Returns candidate paths for motor calibration data in order of priority:
    1. Local override backup (motorData_calibrated_local.json)
    2. Local robot calibration (motorData_calibrated.json - git-ignored)
    3. Versioned template (motorData_calibrated.example.json)
    4. Base hardware mapping (motorData.json)
    """
    return [
        PROJECT_ROOT / "motorData_calibrated_local.json",
        PROJECT_ROOT / "motorData_calibrated.json",
        PROJECT_ROOT / "motorData_calibrated.example.json",
        PROJECT_ROOT / "motorData.json",
    ]


def init_local_motor_calibration(force: bool = False) -> Path:
    """
    Initializes the local robot calibration file (motorData_calibrated.json)
    from the template if it does not yet exist.
    """
    target = PROJECT_ROOT / "motorData_calibrated.json"
    if target.exists() and not force:
        return target

    example = PROJECT_ROOT / "motorData_calibrated.example.json"
    if example.exists():
        shutil.copyfile(example, target)
        logger.info(f"Initialized local robot calibration file at {target} from template.")
    else:
        save_motor_calibration(DEFAULT_MOTOR_MAP, custom_path=target)
    return target


def is_motor_calibrated(custom_path: Optional[Path] = None) -> bool:
    """
    Determines whether the physical robot motors have been calibrated locally.
    
    Returns False if:
    1. Local calibration file does not exist.
    2. The profile explicitly defines 'system_calibrated': False.
    3. Any of the required motors is marked 'calibrated': False.
    4. All joints still have the default uncalibrated dummy bounds (e.g. min 290, max 310).
    5. The contents match the basic motorData_calibrated.example.json template.
    """
    if custom_path is not None:
        active_path = Path(custom_path)
    else:
        local_file = PROJECT_ROOT / "motorData_calibrated.json"
        local_backup = PROJECT_ROOT / "motorData_calibrated_local.json"
        active_path = local_backup if local_backup.exists() else local_file

    if not active_path.exists():
        return False

    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Error reading motor calibration file {active_path}: {e}")
        return False

    # 1. Top-level system_calibrated flag check
    if data.get("system_calibrated") is False:
        return False

    # 2. Check if identical to example template
    example_file = PROJECT_ROOT / "motorData_calibrated.example.json"
    if example_file.exists() and active_path != example_file:
        try:
            with open(example_file, "r", encoding="utf-8") as ef:
                example_data = json.load(ef)
            joints = ["neck", "torso", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow"]
            if all(data.get(j) == example_data.get(j) for j in joints if j in example_data):
                # Data is completely unchanged from the uncalibrated template
                return False
        except Exception:
            pass

    # 3. Check individual joints for calibration flag and dummy values
    required_joints = ["neck", "torso", "left_shoulder", "right_shoulder"]
    has_custom_values = False
    for joint in required_joints:
        joint_data = data.get(joint)
        if not isinstance(joint_data, dict):
            return False
        if not joint_data.get("calibrated", False):
            return False
        # If any joint has bounds other than the dummy 290..310, it has been calibrated
        if joint_data.get("min") != 290 or joint_data.get("max") != 310:
            has_custom_values = True

    return has_custom_values


def get_calibration_status(custom_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns a dictionary describing the robot's motor calibration state."""
    calibrated = is_motor_calibrated(custom_path=custom_path)
    if custom_path is not None:
        active_path = Path(custom_path)
    else:
        local_file = PROJECT_ROOT / "motorData_calibrated.json"
        local_backup = PROJECT_ROOT / "motorData_calibrated_local.json"
        active_path = local_backup if local_backup.exists() else (local_file if local_file.exists() else None)

    calibrated_at = None
    reason = "ok" if calibrated else "uncalibrated"
    if active_path and active_path.exists():
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            calibrated_at = d.get("calibrated_at")
            if d.get("system_calibrated") is False:
                reason = "system_flag_false"
            elif not calibrated:
                reason = "uncalibrated_joints"
        except Exception:
            reason = "read_error"
    else:
        reason = "file_not_found"

    return {
        "calibrated": calibrated,
        "reason": reason,
        "local_file_exists": active_path is not None and active_path.exists(),
        "active_path": str(active_path) if active_path else None,
        "calibrated_at": calibrated_at,
    }


def load_motor_calibration(auto_init: bool = False) -> Dict[str, Dict[str, Any]]:
    """Loads motor calibration parameters from disk, falling back to safe defaults."""
    local_file = PROJECT_ROOT / "motorData_calibrated.json"
    local_backup = PROJECT_ROOT / "motorData_calibrated_local.json"

    # Auto-initialize local file only if explicitly requested
    if auto_init and not local_file.exists() and not local_backup.exists():
        try:
            init_local_motor_calibration()
        except Exception as e:
            logger.warning(f"Could not auto-initialize local calibration: {e}")

    for path in get_motor_calibration_paths():
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded motor calibration from {path}")
                # Filter out metadata keys like system_calibrated and calibrated_at when returning motor dict
                return {k: v for k, v in data.items() if isinstance(v, dict) and "channel" in v}
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")

    logger.info("Using built-in default motor calibration profile.")
    return {k: v for k, v in DEFAULT_MOTOR_MAP.items() if isinstance(v, dict) and "channel" in v}


def save_motor_calibration(data: Dict[str, Any], custom_path: Optional[Path] = None) -> Path:
    """
    Saves motor calibration profile to disk.
    Always targets the robot-local, untracked motorData_calibrated.json by default.
    Keeps motorData_calibrated_local.json in sync if present.
    """
    target_path = custom_path or (PROJECT_ROOT / "motorData_calibrated.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    logger.info(f"Saved motor calibration to {target_path}")

    # Keep local backup in sync if present
    local_backup = PROJECT_ROOT / "motorData_calibrated_local.json"
    if custom_path is None and local_backup.exists() and local_backup != target_path:
        try:
            with open(local_backup, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Synced motor calibration to {local_backup}")
        except Exception as e:
            logger.warning(f"Could not sync to {local_backup}: {e}")

    return target_path


def load_lookat_calibration() -> Dict[str, Any]:
    """Loads lookat gaze calibration interpolation points safely."""
    candidate_paths = [
        PROJECT_ROOT / "Character" / "lookat_calibrated.json",
        PROJECT_ROOT / "lookat_calibrated.json",
    ]
    for path in candidate_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        return data
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")
    return {}
