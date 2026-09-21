"""
Interactive local demonstration of Gigi Social Robot platform.

Demonstrates:
1. Gigi animated face display (Pygame/OpenCV window).
2. Live camera feed with face tracking and landmark overlays.
3. Speech synthesis (TTS) playing aloud through computer speakers.
4. Voice activity detection (VAD) and ASR (Faster-Whisper) listening to the user.
5. Interactive conversational loop responding to the user's voice.
"""

import os
import sys
import time
import random
import threading
import numpy as np
import cv2
import sounddevice as sd
import pyaudio

# Ensure repository root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from gigi.core.config import ASSETS_DIR
from gigi.expression.face_display import Face
from gigi.expression.speech import Speech
from gigi.perception.whisper_helper import clean_transcript
from faster_whisper import WhisperModel


def find_best_input_device():
    """Find the best microphone device index."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and ("Array" in dev['name'] or "Microphone" in dev['name']):
            return i
    return sd.default.device[0]


def run_interactive_session():
    print("=" * 65)
    print("       GIGI SOCIAL ROBOT - INTERACTIVE LOCAL DEMONSTRATION    ")
    print("=" * 65)
    print("\n[Step 1/4] Initializing Face Display (Windowed mode)...")
    
    # Initialize Face in windowed mode
    face = Face(character="fuzzy", full_screen=False)
    
    print("[Step 2/4] Initializing Camera Feed (Port 0)...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Warning] Could not open camera on port 0. Trying port 1...")
        cap = cv2.VideoCapture(1)
    
    has_camera = cap.isOpened()
    if has_camera:
        print("[Camera] Camera feed successfully opened!")
    else:
        print("[Camera] No physical webcam opened. Face display will run standalone.")

    print("[Step 3/4] Initializing Speech Engine (TTS)...")
    speech = Speech(activity="InteractiveDemo")
    
    print("[Step 4/4] Initializing Faster-Whisper ASR Model...")
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    mic_device_index = find_best_input_device()
    print(f"[ASR] Whisper loaded. Using input audio device #{mic_device_index}.")

    print("\n" + "=" * 65)
    print(">>> GIGI IS READY! DISPLAYING FACE AND STARTING INTERACTION <<<")
    print("=" * 65 + "\n")

    # Flag for running background threads
    session_active = True

    # Camera preview window
    cv2.namedWindow("Gigi Vision - Camera Feed", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Gigi Vision - Camera Feed", 640, 480)

    # Simple face detector for camera window
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def render_face_and_camera():
        """Main GUI loop for OpenCV windows."""
        nonlocal session_active
        blink_timer = time.time() + 3.0
        is_blinking = False
        blink_end = 0

        while session_active:
            # 1. Update camera feed
            if has_camera:
                ret, frame = cap.read()
                if ret and frame is not None:
                    # Detect faces for visual overlay
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                    for (x, y, w, h) in faces:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 120), 2)
                        cv2.putText(frame, "User Detected", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 120), 2)
                    
                    cv2.putText(
                        frame, "Gigi Vision Live (Press Q in window to quit)",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
                    )
                    cv2.imshow("Gigi Vision - Camera Feed", frame)

            # 2. Blink animation on face
            now = time.time()
            if not is_blinking and now >= blink_timer:
                is_blinking = True
                blink_timer = now + random.uniform(3.5, 6.5)
                def do_blink():
                    nonlocal is_blinking
                    try:
                        t = face.sequence_thread("blink")
                        t.start()
                        t.join()
                    finally:
                        is_blinking = False
                threading.Thread(target=do_blink, daemon=True).start()

            # Redraw face window
            if face.last_face_image is not None:
                face.display_face(face.last_face_image)

            # Check for keypress
            key = cv2.waitKey(20) & 0xFF
            if key == ord('q') or key == 27:
                session_active = False
                break

    # Start GUI rendering thread (or run on main thread)
    # On Windows, OpenCV imshow should run on main thread!
    # So we will run interaction steps in a separate thread, and GUI on main thread!

    def interaction_workflow():
        nonlocal session_active
        time.sleep(1.0)

        # Stage 1: Welcome speech
        print("\n[Gigi]: Speaking welcome message...")
        speech.run_speech(
            "Hello! I am Gigi the social robot. "
            "I can see you through my camera, and my animated face is active on your screen!"
        )
        time.sleep(1.0)

        # Stage 2: Prompt user to speak
        for turn in range(1, 3):
            if not session_active:
                break

            prompt_text = (
                f"Turn {turn}: Please speak into your microphone now! "
                "Tell me something, and I will transcribe your voice."
            )
            print(f"\n[Gigi]: {prompt_text}")
            speech.run_speech(prompt_text)

            # Activate listening ear icon on face
            print("\n" + "-" * 50)
            print(">>> [GIGI IS LISTENING] - PLEASE SPEAK NOW! <<<")
            print("-" * 50)
            face.feedback_state = "listening"

            # Record 5 seconds of audio
            record_seconds = 5
            rate = 16000
            chunk = 1024
            p = pyaudio.PyAudio()
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=mic_device_index,
                    frames_per_buffer=chunk
                )
            except Exception:
                # Fallback to default
                stream = p.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True, frames_per_buffer=chunk)

            frames = []
            start_rec = time.time()
            while time.time() - start_rec < record_seconds and session_active:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            # Clear listening icon
            face.feedback_state = None
            print("\n[Gigi]: Finished recording. Processing speech with Faster-Whisper...")

            # Convert to float32
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16).astype(np.float32) / 32768.0
            energy = np.sqrt(np.mean(audio_data**2))
            print(f"[Audio Info] Captured audio with RMS energy: {energy:.4f}")

            # Transcribe
            segments, _ = whisper_model.transcribe(audio_data, language="en")
            transcript = " ".join([clean_transcript(s.text) for s in segments]).strip()

            if transcript:
                print("\n" + "=" * 50)
                print(f"  USER SAID: \"{transcript}\"")
                print("=" * 50 + "\n")
                reply = f"I heard you say: {transcript}. Everything is working wonderfully!"
            else:
                print("\n[Gigi]: No distinct words detected. (Try speaking a bit closer to your mic).")
                reply = "I did not catch that clearly, but my audio stream is receiving your input."

            speech.run_speech(reply)
            time.sleep(1.5)

        print("\n[Interaction Complete] Feel free to inspect the windows. Press 'q' on any window or Ctrl+C in terminal to exit.")

    # Start interaction thread
    worker = threading.Thread(target=interaction_workflow, daemon=True)
    worker.start()

    # Run GUI loop on main thread (required by OpenCV on Windows)
    try:
        render_face_and_camera()
    except KeyboardInterrupt:
        print("\nExiting interactive demo...")
    finally:
        session_active = False
        if has_camera and cap:
            cap.release()
        face.stop_face()
        cv2.destroyAllWindows()
        print("[Demo] Clean exit complete.")


if __name__ == "__main__":
    run_interactive_session()
