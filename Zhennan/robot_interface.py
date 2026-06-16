import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(current_dir)
char_dir = os.path.join(gigi_dir, "Character")

if gigi_dir not in sys.path:
    sys.path.insert(0, gigi_dir)
if char_dir not in sys.path:
    sys.path.insert(0, char_dir)
import re
import time
from Character.vision import Vision
from Character.speech import Speech
from Character.hearing import Hearing


class RobotInterface:
    """
    Unified interface connecting the activity pipeline to the robot's
    physical capabilities: Speech (TTS), Hearing (STT), and Vision (camera).

    Usage
    -----
        robot = RobotInterface()
        robot.start()                  # boots vision + camera
        robot.speak("Hello!")          # speaks and executes non-verbal cues
        text = robot.listen()          # blocks until student finishes speaking
        ctx  = robot.get_vision_context()  # snapshot of who's visible + emotions
        robot.stop()                   # clean shutdown
    """

    def __init__(self, pause_vision_during_speech: bool = True, child_voice: bool = True):
        self.pause_vision_during_speech = pause_vision_during_speech

        # --- Vision ---
        self.vision = Vision(None, auto_start=False)
        self.vision.is_robot = True
        self.vision.set_processing_flags({
            "face_detection":   2.0,
            "face_recognition": 2.0,
            "emotion":          2.0,
            "gesture":          5.0,
        })

        # --- Speech (TTS) ---
        self.speech = Speech(languages="en", child=child_voice)
        self.speech.set_activity("educational_activity")

        # --- Hearing (STT) ---
        self.hearing = Hearing(verbose=False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the vision system and wait for the camera to come up."""
        print("[RobotInterface] Starting vision system…")
        self.vision.run_vision()

        # Give the camera up to 3 s to produce its first frame
        for _ in range(15):
            if self.vision.get_latest_frame() is not None:
                break
            time.sleep(0.2)

        print("[RobotInterface] Ready.")

    def stop(self):
        """Gracefully shut everything down."""
        print("[RobotInterface] Shutting down…")
        self.vision.stop_vision()
        self.vision.cleanup()

    # ------------------------------------------------------------------
    # Speaking
    # ------------------------------------------------------------------

    def speak(self, text: str):
        """
        Speak *text* aloud.

        Non-verbal cues written as [smile], [wave hands] etc. are stripped
        so the TTS never reads them out loud.
        """
        if self.pause_vision_during_speech:
            self._pause_vision()

        clean_text = self._strip_nonverbals(text)
        if clean_text:
            self.speech.run_speech(text=clean_text)

        if self.pause_vision_during_speech:
            self._resume_vision()

    # ------------------------------------------------------------------
    # Listening
    # ------------------------------------------------------------------

    def listen(self) -> str | None:
        """
        Block until the student finishes speaking.

        Returns the transcribed string, or None if nothing was heard.
        """
        self.hearing.texts = []
        self.hearing.run_hearing()

        if self.hearing.texts:
            return self.hearing.texts[-1]

        return None

    # ------------------------------------------------------------------
    # Vision context for LLM prompts
    # ------------------------------------------------------------------

    def get_vision_context(self) -> str:
        """
        Return a one-line natural-language description of what the camera
        currently sees.  This is injected into LLM prompts so the model
        is aware of student emotions and gestures.

        Example output:
            "Vision: Alice (happy), Bob (neutral, gesturing: Thumbs Up)"
        """
        try:
            all_faces = self.vision.face_cache.get_all_faces()
            if not all_faces:
                return "Vision: no students detected."

            parts = []
            for info in all_faces.values():
                name    = info.get("name", "Unknown")
                emotion = info.get("emotion", "")
                gesture = info.get("gesture", "Unknown")

                desc = name
                details = []
                if emotion and emotion not in ("unknown", ""):
                    details.append(emotion)
                if gesture and gesture not in ("Unknown", ""):
                    details.append(f"gesturing: {gesture}")
                if details:
                    desc += f" ({', '.join(details)})"
                parts.append(desc)

            return "Vision: " + "; ".join(parts)

        except Exception as exc:
            return f"Vision: unavailable ({exc})"

    def get_present_students(self) -> list[str]:
        """Return names of recognised students currently visible to the camera."""
        try:
            all_faces = self.vision.face_cache.get_all_faces()
            return [
                info["name"]
                for info in all_faces.values()
                if info.get("name") not in ("Unknown", "Recognizing...", "")
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _strip_nonverbals(self, text: str) -> str:
        """
        Remove non-verbal cues (anything in square brackets that is not a
        system tag like STRATEGY or NEXT_STEP) so TTS never reads them aloud.
        """
        system_tags = {"STRATEGY", "NEXT_STEP"}

        def _replacer(m):
            content = m.group(1).strip()
            if any(content.upper().startswith(tag) for tag in system_tags):
                return m.group(0)   # keep system tags intact for callers
            return ""               # drop non-verbal cues

        clean = re.sub(r"\[([^\]]+)\]", _replacer, text).strip()
        return re.sub(r" {2,}", " ", clean).strip()

    def _pause_vision(self):
        self.vision.set_processing_flags({
            "face_detection": 0, "face_recognition": 0,
            "emotion": 0,        "gesture": 0,
        })
        time.sleep(0.1)

    def _resume_vision(self):
        self.vision.set_processing_flags({
            "face_detection":   2.0,
            "face_recognition": 2.0,
            "emotion":          2.0,
            "gesture":          5.0,
        })
        time.sleep(0.1)