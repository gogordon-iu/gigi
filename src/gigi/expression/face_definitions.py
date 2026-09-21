"""
Face part definitions, sprite sequences, and animation parameters for Gigi.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Any
from gigi.core.config import ASSETS_DIR

FACE_IMAGE_DIR = ASSETS_DIR / "face"

GLOBAL_PARTS = ["Eyes", "Nose", "Mouth"]

CHARACTERS: Dict[str, Dict[str, Any]] = {
    "gigi": {
        "name": "gigi",
        "base_image_name": "robot face.00",
        "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
        "part_sequence": {
            "Eyes": [("idle", [1]), ("blink", list(range(1, 8)))],
            "Mouth": [("idle", [1]), ("talk", list(range(1, 5)))],
            "Nose": [("idle", [1])],
        },
    },
    "fuzzy": {
        "name": "fuzzy",
        "base_image_name": "fuzzy face.",
        "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
        "part_sequence": {
            "Eyes": [
                ("idle", [1]),
                ("blink", list(range(1, 8))),
                ("look_right", [10, 11]),
                ("look_left", [12, 13]),
                ("look_down", [15]),
                ("look_up", [14]),
            ],
            "Mouth": [("idle", [1]), ("talk", list(range(1, 5))), ("smile", [8, 9])],
            "Nose": [("idle", [1])],
        },
    },
    "tutti": {
        "name": "tutti",
        "base_image_name": "tutti face.00",
        "part_slices": {"Eyes": [0, 0.41], "Nose": [0.41, 0.65], "Mouth": [0.65, 1]},
        "part_sequence": {
            "Eyes": [("idle", [1]), ("blink", list(range(1, 8)))],
            "Mouth": [("idle", [1]), ("talk", list(range(1, 5)))],
            "Nose": [("idle", [1])],
        },
    },
}

# Build basic lookup sequences
BASIC_SEQUENCES: Dict[str, Dict[str, Tuple[str, List[str]]]] = {}
for part, part_seq in CHARACTERS["fuzzy"]["part_sequence"].items():
    for seq in part_seq:
        BASIC_SEQUENCES[seq[0]] = {part: (seq[0], [str(i) for i in seq[1]])}

# Backwards-compatibility aliases
characters = CHARACTERS
global_parts = GLOBAL_PARTS
basic_sequences = BASIC_SEQUENCES
image_folder_path = str(FACE_IMAGE_DIR) + "/"
