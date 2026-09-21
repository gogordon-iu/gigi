"""
Viseme lip-syncing engine for Gigi robot.
Analyzes audio amplitude envelopes to synchronize 2D mouth animations with speech.
"""

import time
import threading
import re
from typing import Optional, Dict, Any, List

from gigi.expression.face_display import Face
from gigi.expression.speech import Speech


class Viseme:
    """
    Coordinates simultaneous audio playback and mouth viseme animations.
    """

    def __init__(self, face: Optional[Face] = None, speech: Optional[Speech] = None, character_name: str = "fuzzy"):
        self.face = face if face is not None else Face(character=character_name, full_screen=True)
        self.speech = speech if speech is not None else Speech()
        self.sync_offset = 0.0
        self.character = None

    def set_viseme(self, envelope_: List[float]) -> Dict[str, Any]:
        """Maps an audio amplitude envelope into a sequence of mouth animation indices."""
        mouth_sequences = self.face.character["part_sequence"]["Mouth"]
        talk_length = 4
        for seq in mouth_sequences:
            if seq[0] == "talk":
                talk_length = len(seq[1])
                break

        talk_sequence = {
            "Mouth": ("talk", [str(min(talk_length, int(env * talk_length) + 1)) for env in envelope_])
        }
        return talk_sequence

    def generate_viseme_sequence(self, text: Optional[str] = None, file: Optional[str] = None):
        """Generates the mouth frame sequence without playing audio."""
        actual_file = self.speech.update_audio_objects(file=file, text=text)
        if actual_file and actual_file in self.speech.audio_objects:
            envelope = self.speech.audio_objects[actual_file]["envelope"]
            return self.set_viseme(envelope)
        return None

    def run_viseme(self, text: Optional[str] = None, file: Optional[str] = None) -> None:
        """
        Synchronously coordinates audio playback and mouth viseme rendering.
        """
        if hasattr(self, "character") and self.character:
            if text:
                if not hasattr(self.character, "activity_log"):
                    self.character.activity_log = []
                if not self.character.activity_log or self.character.activity_log[-1].get("text") != text:
                    self.character.activity_log.append({
                        "speaker": "Gigi",
                        "text": text,
                        "timestamp": time.time(),
                    })
            elif file:
                if not hasattr(self.character, "activity_log"):
                    self.character.activity_log = []
                self.character.activity_log.append({
                    "speaker": "Gigi",
                    "text": f"[Plays audio file: {file}]",
                    "timestamp": time.time(),
                })

            # Check for gaze redirection to recognized individuals
            if text and hasattr(self.character, "egocentric_db"):
                matched_name = None
                for name in self.character.egocentric_db.keys():
                    if re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
                        matched_name = name
                        break
                if matched_name and hasattr(self.character, "lookat_person"):
                    print(f"[Viseme Gaze] Matched '{matched_name}' in viseme text: redirecting gaze.")
                    self.character.lookat_person(matched_name)

        # 1. Update/generate audio object
        actual_file = self.speech.update_audio_objects(file=file, text=text)
        if not actual_file or actual_file not in self.speech.audio_objects:
            print("ERROR: Could not load or generate speech audio.")
            return

        # 2. Extract envelope and build mouth sequence
        envelope = self.speech.audio_objects[actual_file]["envelope"]
        talk_sequence = self.set_viseme(envelope)

        # 3. Synchronize playback
        start_time_container = [None]
        stop_event = threading.Event()

        speech_thread = threading.Thread(
            target=self.speech.play_audio,
            args=(actual_file, stop_event, start_time_container, "audio"),
            daemon=True,
        )
        speech_thread.start()

        # Wait until audio actually begins
        while start_time_container[0] is None:
            time.sleep(0.001)

        start_time = start_time_container[0]
        self.face.generate_face(
            parts_selected=talk_sequence,
            stop_event=stop_event,
            stop_condition=None,
            delay=self.speech.sample_rate,
            start_time=start_time - self.sync_offset,
        )

        speech_thread.join()
