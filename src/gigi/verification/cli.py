"""
Unified verification and diagnostic CLI for Gigi robot subsystems.

Usage:
    gigi-verify camera
    gigi-verify motors
    gigi-verify screen
    gigi-verify speaker
    gigi-verify mic
    gigi-verify gestures
    gigi-verify face
    gigi-verify stt
    gigi-verify tts
    gigi-verify llm
    gigi-verify all
"""

import sys
import argparse
import logging
from typing import List

logger = logging.getLogger("gigi.verification")


def test_camera():
    print("\n--- [VERIFY] Camera Subsystem ---")
    from gigi.hardware.camera import find_camera_ports, open_camera
    ports = find_camera_ports()
    print(f"Detected camera ports: {ports}")
    if ports:
        cap = open_camera(ports[0])
        if cap and cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                print(f"[PASS] Successfully captured frame: shape {frame.shape}")
                return True
    print("[FAIL] Could not capture frame from any camera.")
    return False


def test_motors():
    print("\n--- [VERIFY] Motor / PCA9685 Subsystem ---")
    from gigi.hardware.motors import PCA9685Controller
    from gigi.hardware.calibration import load_motor_calibration
    motors = PCA9685Controller()
    calib = load_motor_calibration()
    print(f"Loaded calibration for {len(calib)} motors: {list(calib.keys())}")
    print(f"Hardware available: {motors.is_hardware_available}")
    if motors.is_hardware_available:
        print("[PASS] PCA9685 I2C communication verified.")
        return True
    else:
        print("[INFO] Running in simulation mode (I2C bus not opened).")
        return True


def test_gestures():
    print("\n--- [VERIFY] Gestures Subsystem ---")
    from gigi.expression.movement import Movement
    from gigi.expression.gesture_definitions import BASIC_GESTURES
    print(f"Available gestures: {list(BASIC_GESTURES.keys())}")
    try:
        m = Movement()
        print("[PASS] Movement kinematics initialized successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Error initializing movement: {e}")
        return False


def test_screen():
    print("\n--- [VERIFY] Screen / Display Subsystem ---")
    from gigi.expression.face_definitions import CHARACTERS
    print(f"Configured characters: {list(CHARACTERS.keys())}")
    try:
        from gigi.expression.face_display import Face
        print("[PASS] Face rendering module loaded successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Error loading face display: {e}")
        return False


def test_audio():
    print("\n--- [VERIFY] Audio / Speaker Subsystem ---")
    try:
        from gigi.expression.speech import Speech
        speech = Speech()
        print(f"[PASS] Speech synthesis engine loaded (sample rate: {speech.sample_rate}).")
        return True
    except Exception as e:
        print(f"[FAIL] Speech engine failure: {e}")
        return False


def test_mic():
    print("\n--- [VERIFY] Microphone / Hearing Subsystem ---")
    try:
        from gigi.perception.hearing import Hearing
        hearing = Hearing()
        print("[PASS] Audio capture & hearing pipeline initialized.")
        return True
    except Exception as e:
        print(f"[FAIL] Hearing initialization failure: {e}")
        return False


def test_face():
    print("\n--- [VERIFY] Face Recognition & Vision Subsystem ---")
    try:
        from gigi.perception.vision_helper import FaceDatabase, EmotionDetector
        db = FaceDatabase()
        print(f"[PASS] Face database loaded ({len(db.known_names)} registered faces).")
        return True
    except Exception as e:
        print(f"[FAIL] Vision / Face database failure: {e}")
        return False


def test_llm():
    print("\n--- [VERIFY] LLM Subsystem ---")
    try:
        from gigi.interaction.llm.client import LLMClient
        client = LLMClient()
        print(f"[PASS] LLM client initialized for: {client.base_url} (model: {client.model})")
        return True
    except Exception as e:
        print(f"[FAIL] LLM client configuration error: {e}")
        return False


def test_stt():
    print("\n--- [VERIFY] Speech-to-Text (STT) Subsystem ---")
    try:
        from faster_whisper import WhisperModel
        print("[PASS] faster_whisper module available.")
        return True
    except Exception as e:
        print(f"[FAIL] Speech-to-Text dependency error: {e}")
        return False


def test_tts():
    print("\n--- [VERIFY] Text-to-Speech (TTS) Subsystem ---")
    try:
        from gigi.expression.speech import Speech
        speech = Speech()
        print(f"[PASS] Text-to-Speech engine initialized (sample rate: {speech.sample_rate}).")
        return True
    except Exception as e:
        print(f"[FAIL] Text-to-Speech engine error: {e}")
        return False


VERIFIERS = {
    "camera": test_camera,
    "motors": test_motors,
    "gestures": test_gestures,
    "screen": test_screen,
    "speaker": test_audio,
    "mic": test_mic,
    "face": test_face,
    "llm": test_llm,
    "stt": test_stt,
    "tts": test_tts,
}


def run_verification(targets: List[str]) -> bool:
    results = {}
    if "all" in targets:
        to_run = list(VERIFIERS.keys())
    else:
        to_run = [t for t in targets if t in VERIFIERS]

    for name in to_run:
        try:
            results[name] = VERIFIERS[name]()
        except Exception as e:
            print(f"[ERROR] Subsystem '{name}' threw an uncaught exception: {e}")
            results[name] = False

    print("\n==========================================")
    print("       GIGI VERIFICATION SUMMARY          ")
    print("==========================================")
    all_passed = True
    for name, success in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"  {name.upper():<12} : {status}")
        if not success:
            all_passed = False
    print("==========================================")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Gigi Robot Hardware & AI Subsystem Verification")
    parser.add_argument(
        "subsystem",
        nargs="*",
        default=["all"],
        choices=["all", "camera", "motors", "gestures", "screen", "speaker", "mic", "face", "llm", "stt", "tts"],
        help="Subsystem(s) to verify (default: all)",
    )
    args = parser.parse_args()
    success = run_verification(args.subsystem)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
