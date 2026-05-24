import sys
import os

char_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(char_dir)
base_assets_path = os.path.join(gigi_dir, 'Assets', '').replace('\\', '/')

IS_ROBOT = sys.platform.startswith("linux")

# Runtime execution flags for NPU vs CPU (Orange Pi 5 Pro)
# USE_NPU_TRANSCRIPTION: If True, uses the local NPU-accelerated SenseVoiceSmall model on Orange Pi.
#                         If False, falls back to faster-whisper on CPU (suitable for Windows testing).
USE_NPU_TRANSCRIPTION = IS_ROBOT  # Default: True on Linux (Orange Pi), False on Windows

# USE_NPU_SPEAKER: If True, uses the RKNN-compiled VoiceEncoder model on the NPU.
#                  If False, runs the standard PyTorch VoiceEncoder model on CPU.
#                  (Note: CPU execution is recommended to prevent NPU scheduling bottlenecks and resource contention).
USE_NPU_SPEAKER = False  # Default: False (keeps PyTorch CPU to run in parallel with NPU transcription)

if IS_ROBOT:
    HAS_FACE = True
    HAS_SPEECH = True
    HAS_VISEME = True

    HAS_HEARING = True
    HAS_VISION = True

    HAS_MOVEMENT = True
    HAS_CONVERSATION = True
else:
    HAS_FACE = True
    HAS_SPEECH = True
    HAS_VISEME = True

    HAS_HEARING = True
    HAS_VISION = True

    HAS_MOVEMENT = False
    HAS_CONVERSATION = True

# Paths
CHARACTER_FOLDER = char_dir.replace('\\', '/') + '/'

# Follow face thresholds:
FOLLOW_TORSO_OFFSET = 0.5
FOLLOW_NECK_OFFSET = 0.25
FOLLOW_EYES_OFFSET = 0.1
OFFSET_TORSO_RATIO = 0.3        # how much torso should move to put the face in the middle again
OFFSET_NECK_RATIO = 0.2
TORSO_FOLLOW_DURATION = 1.0     # seconds
NECK_FOLLOW_DURATION = 1.0     # seconds