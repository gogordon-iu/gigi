import sys

base_assets_path = "../Assets/"

IS_ROBOT = sys.platform.startswith("linux")

if IS_ROBOT:
    HAS_FACE = True
    HAS_SPEECH = True
    HAS_VISEME = True

    HAS_HEARING = True
    HAS_VISION = True

    HAS_MOVEMENT = True
    HAS_CONVERSATION = False
else:
    HAS_FACE = False
    HAS_SPEECH = True
    HAS_VISEME = False

    HAS_HEARING = False
    HAS_VISION = False

    HAS_MOVEMENT = False
    HAS_CONVERSATION = False

# Paths
from pathlib import Path
current_directory = (str)(Path.cwd())
CHARACTER_FOLDER = current_directory.split("gigi")[0] + "gigi/Character/"

# Follow face thresholds:
FOLLOW_TORSO_OFFSET = 0.5
FOLLOW_NECK_OFFSET = 0.25
FOLLOW_EYES_OFFSET = 0.1
OFFSET_TORSO_RATIO = 0.3        # how much torso should move to put the face in the middle again
OFFSET_NECK_RATIO = 0.2
TORSO_FOLLOW_DURATION = 1.0     # seconds
NECK_FOLLOW_DURATION = 1.0     # seconds