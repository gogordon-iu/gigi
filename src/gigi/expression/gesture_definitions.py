"""
Predefined gesture trajectories and motor sequences for Gigi robot.
Angles are normalized from -1.0 to 1.0 (clamped by motor calibration limits).
"""

from typing import Dict, List, Any

# Predefined motor motion sequences
BASIC_GESTURES: Dict[str, List[Dict[str, Any]]] = {}

BASIC_GESTURES["home"] = [
    {
        "time": 1.0,
        "motors": {
            "neck": 0.0,
            "right_shoulder": 0.0,
            "left_shoulder": 0.0,
            "right_elbow": 0.0,
            "left_elbow": 0.0,
            "torso": 0.0,
        },
    }
]

BASIC_GESTURES["wave_hello"] = [
    {"time": 0.4, "motors": {"right_shoulder": 0.8, "right_elbow": 0.0}},
    {"time": 0.65, "motors": {"right_elbow": -0.8}},
    {"time": 0.9, "motors": {"right_elbow": 0.8}},
    {"time": 1.15, "motors": {"right_elbow": -0.8}},
    {"time": 1.4, "motors": {"right_elbow": 0.8}},
    {"time": 1.8, "motors": {"right_shoulder": -0.8, "right_elbow": 0.0}},
]

BASIC_GESTURES["wave_right"] = BASIC_GESTURES["wave_hello"]

BASIC_GESTURES["wave_left"] = []
for step in BASIC_GESTURES["wave_right"]:
    mirrored_step = {"time": step["time"], "motors": {}}
    for k, v in step["motors"].items():
        mirrored_step["motors"][k.replace("right", "left")] = -v
    BASIC_GESTURES["wave_left"].append(mirrored_step)

BASIC_GESTURES["open_arms"] = [
    {"time": 1.0, "motors": {"right_shoulder": 0.3, "left_shoulder": -0.3, "right_elbow": 0.0, "left_elbow": 0.0}},
    {"time": 1.5, "motors": {"right_elbow": 0.3, "left_elbow": -0.3}},
    {"time": 2.0, "motors": {"neck": 0.8}},
    {"time": 2.5, "motors": {"neck": -0.8}},
    {"time": 3.0, "motors": {"neck": 0.0, "right_shoulder": -0.3, "left_shoulder": 0.3, "right_elbow": 0.0, "left_elbow": 0.0}},
]

BASIC_GESTURES["open_close_arms"] = [
    {"time": 1.0, "motors": {"right_shoulder": 0.3, "left_shoulder": -0.3, "right_elbow": 0.0, "left_elbow": 0.0}},
    {"time": 1.5, "motors": {"right_elbow": 0.3, "left_elbow": -0.3}},
    {"time": 2.5, "motors": {"right_shoulder": 0.0, "left_shoulder": 0.0, "right_elbow": 0.0, "left_elbow": 0.0}},
]

BASIC_GESTURES["look_from_side_to_side"] = [
    {"time": 1.0, "motors": {"neck": -0.8}},
    {"time": 2.0, "motors": {"neck": 0.8}},
    {"time": 3.0, "motors": {"neck": 0.0}},
]

BASIC_GESTURES["arms_down"] = [
    {"time": 1.0, "motors": {"right_elbow": 0.8, "left_elbow": -0.8, "right_shoulder": -0.8, "left_shoulder": 0.8}}
]

BASIC_GESTURES["arms_up"] = [
    {"time": 1.0, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": 0.3, "left_shoulder": -0.3}}
]

BASIC_GESTURES["arms_up_and_down"] = [
    {"time": 1.0, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": 0.3, "left_shoulder": 0.3}},
    {"time": 3.0, "motors": {"right_shoulder": -0.3, "left_shoulder": -0.3}},
    {"time": 4.0, "motors": {"right_shoulder": 0.0, "left_shoulder": 0.0}},
]

BASIC_GESTURES["clap"] = [
    {"time": 1.0, "motors": {"right_elbow": 0.8, "left_elbow": -0.8, "right_shoulder": 0.0, "left_shoulder": 0.0}},
    {"time": 1.2, "motors": {"right_elbow": -0.8, "left_elbow": 0.8}},
    {"time": 1.4, "motors": {"right_elbow": 0.8, "left_elbow": -0.8}},
    {"time": 1.6, "motors": {"right_elbow": -0.8, "left_elbow": 0.8}},
    {"time": 1.8, "motors": {"right_elbow": 0.8, "left_elbow": -0.8}},
    {"time": 2.0, "motors": {"right_shoulder": -0.8, "left_shoulder": 0.8}},
]

BASIC_GESTURES["arms_circle"] = [
    {"time": 0.2, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": 0.8, "left_shoulder": -0.8}},
    {"time": 0.4, "motors": {"right_elbow": 0.8, "left_elbow": -0.8, "right_shoulder": 0.0, "left_shoulder": 0.0}},
    {"time": 0.6, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": -0.8, "left_shoulder": 0.8}},
    {"time": 0.8, "motors": {"right_elbow": -0.8, "left_elbow": 0.8, "right_shoulder": 0.0, "left_shoulder": 0.0}},
    {"time": 1.0, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": 0.8, "left_shoulder": -0.8}},
]

BASIC_GESTURES["scare"] = [
    {"time": 0.0, "motors": {"right_elbow": 0.0, "left_elbow": 0.0, "right_shoulder": 0.8, "left_shoulder": -0.8, "torso": 0.2}},
    {"time": 3.0, "motors": {"neck": 0.0, "right_shoulder": 0.0, "left_shoulder": 0.0, "right_elbow": 0.0, "left_elbow": 0.0, "torso": 0.0}},
]

BASIC_GESTURES["look_left"] = [{"time": 1.0, "motors": {"neck": 0.8}}]
BASIC_GESTURES["look_right"] = [{"time": 1.0, "motors": {"neck": -0.8}}]

BASIC_GESTURES["alive_look_around"] = [
    {"time": 1.0, "motors": {"neck": -0.2, "torso": 0.1}},
    {"time": 2.5, "motors": {"neck": 0.2, "torso": -0.1}},
    {"time": 4.0, "motors": {"neck": 0.0, "torso": 0.0}},
]

BASIC_GESTURES["alive_gently_look_left"] = [
    {"time": 1.5, "motors": {"neck": 0.25, "torso": 0.15}},
    {"time": 3.0, "motors": {"neck": 0.0, "torso": 0.0}},
]

BASIC_GESTURES["alive_gently_look_right"] = [
    {"time": 1.5, "motors": {"neck": -0.25, "torso": -0.15}},
    {"time": 3.0, "motors": {"neck": 0.0, "torso": 0.0}},
]

BASIC_GESTURES["alive_shift"] = [
    {"time": 1.0, "motors": {"neck": 0.1, "torso": -0.08}},
    {"time": 2.0, "motors": {"neck": -0.1, "torso": 0.08}},
    {"time": 3.0, "motors": {"neck": 0.0, "torso": 0.0}},
]

# Backwards compatibility alias
basic_sequences = BASIC_GESTURES
