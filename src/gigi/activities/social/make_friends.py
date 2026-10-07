"""
Make Friends & Social Registration Activity for Gigi robot.
Enables Gigi to meet new friends, capture their face crop and voice profile,
confirm their name with gesture/speech recognition, and save to local databases.
"""

import os
import sys
import time
import re
import threading
from typing import Optional

import cv2
import numpy as np

from gigi.core.robot import Character
from gigi.perception.speaker_id import SpeakerDatabase


def pause_vision(gigi):
    """Temporarily pause intensive vision tasks to maximize CPU/STT performance."""
    if hasattr(gigi, "vision") and gigi.vision:
        print("[MakeFriends] Pausing intensive vision processing for audio listening...")
        gigi.vision.set_processing_flags({
            'face_detection': 0,
            'face_recognition': 0,
            'emotion': 0,
            'gesture': 0
        })
        time.sleep(0.2)


def resume_vision(gigi):
    """Resume standard vision processing after listening."""
    if hasattr(gigi, "vision") and gigi.vision:
        print("[MakeFriends] Resuming vision processing...")
        gigi.vision.set_processing_flags({
            'face_detection': 8.0,
            'face_recognition': 8.0,
            'emotion': 0,
            'gesture': 8.0
        })
        time.sleep(0.2)


def display_captured_face(gigi, face_crop: np.ndarray, name: str):
    """Displays the captured face of the child on Gigi's screen with their name."""
    if not hasattr(gigi, "face") or not gigi.face:
        return

    gigi.face.overlay_text = name

    if getattr(gigi.face, "IMAGE_OPTION", "pygame") == "pygame":
        try:
            import pygame
            rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            h, w = rgb_crop.shape[:2]
            pg_surface = pygame.image.fromstring(rgb_crop.tobytes(), (w, h), "RGB")
            gigi.face.display_face(pg_surface)
        except Exception as e:
            print(f"[MakeFriends] Error displaying face via Pygame: {e}")
    else:
        gigi.face.display_face(face_crop)
    print(f"[MakeFriends] Displaying face crop for '{name}' on screen.")


def verify_name_step(gigi, timeout: float = 10.0) -> Optional[str]:
    """
    Concurrent verification subroutine.
    Checks for Thumbs Up / Thumbs Down gesture in background thread while
    verbally listening for affirmation (yes/no) in main thread.
    Returns: 'yes', 'no', or None.
    """
    gesture_result = [None]
    stop_gesture_thread = threading.Event()

    def gesture_poller():
        start_t = time.time()
        while not stop_gesture_thread.is_set() and (time.time() - start_t < timeout):
            if hasattr(gigi, "vision") and gigi.vision:
                all_faces = gigi.vision.face_cache.get_all_faces()
                if all_faces:
                    for face_id, face_info in all_faces.items():
                        gest = face_info.get('gesture', 'Unknown')
                        if gest == 'Thumbs Up':
                            gesture_result[0] = "yes"
                            stop_gesture_thread.set()
                            return
                        elif gest == 'Thumbs Down':
                            gesture_result[0] = "no"
                            stop_gesture_thread.set()
                            return
            time.sleep(0.2)

    # Start gesture scanning in background
    t = threading.Thread(target=gesture_poller, daemon=True)
    t.start()

    # Verbally listen in main thread
    verbal_result = None
    if hasattr(gigi, "hearing") and gigi.hearing:
        gigi.hearing.texts = []
        gigi.listen_backchannel(timeout=timeout)
        heard = " ".join(gigi.hearing.texts).lower().strip()
        print(f"[MakeFriends] Heard verification response: '{heard}'")

        yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's me", "uh-huh"]
        no_patterns = ["no", "nope", "incorrect", "wrong", "that's not me", "uh-uh"]

        def matches_word(pattern, text):
            return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text))

        if any(matches_word(w, heard) for w in yes_patterns):
            verbal_result = "yes"
        elif any(matches_word(w, heard) for w in no_patterns):
            verbal_result = "no"

    stop_gesture_thread.set()
    t.join(timeout=1.0)

    if gesture_result[0] is not None:
        return gesture_result[0]
    return verbal_result


def extract_name(text: str, conversation=None) -> str:
    """Extracts a capitalized first name from natural spoken input."""
    if not text:
        return "Friend"

    clean_text = text.strip().replace(".", "").replace("!", "")
    if conversation and hasattr(conversation, "get_response"):
        try:
            prompt = (
                f"Extract only the person's first name from this statement: '{clean_text}'. "
                f"Return ONLY the capitalized name, nothing else."
            )
            extracted = conversation.get_response(user_prompt=prompt).strip().replace(".", "").replace("!", "")
            if extracted and len(extracted.split()) == 1:
                return extracted.capitalize()
        except Exception as e:
            print(f"[MakeFriends] LLM extraction fallback: {e}")

    # Heuristic fallback: last capitalized token or last word
    words = [w for w in clean_text.split() if w.lower() not in ["my", "name", "is", "i", "am", "call", "me"]]
    if words:
        return words[-1].capitalize()
    return "Friend"


def register_new_friend(gigi, face_id) -> bool:
    """
    Subroutine to register a new unknown face:
    1. Captures child's face crop and encoding.
    2. Asks child's name and extracts it.
    3. Displays child's face on screen and overlays the name.
    4. Asks child to verify verbally or via thumbs up.
    5. Once confirmed, captures voice/speaker enrollment and saves both profiles to databases.
    """
    print(f"\n[MakeFriends] Starting registration process for face_id: {face_id}")

    # 1. Capture face crop and face encoding
    frame = gigi.vision.get_latest_frame() if (hasattr(gigi, "vision") and gigi.vision) else None
    if frame is None:
        print("[MakeFriends] Warning: Camera frame not available.")
        return False

    face_data = gigi.vision.face_cache.get_face_data(face_id)
    if not face_data or 'box' not in face_data:
        print(f"[MakeFriends] Warning: Face data not found for ID: {face_id}")
        return False

    box = face_data['box']
    h, w = frame.shape[:2]
    # Box is normalized [x1, y1, x2, y2]
    ymin = max(0, int(box[1] * h))
    ymax = min(h, int(box[3] * h))
    xmin = max(0, int(box[0] * w))
    xmax = min(w, int(box[2] * w))

    face_crop = frame[ymin:ymax, xmin:xmax]
    face_encoding = face_data.get('encoding')

    # 2. Introduce and ask name
    gigi.run_character(
        viseme_data={'text': "Hello! I don't think we have met yet. What is your name?", 'file': None},
        movement_data='wave_hello'
    )

    pause_vision(gigi)
    gigi.hearing.texts = []
    gigi.listen_backchannel(timeout=8)
    spoken_name = " ".join(gigi.hearing.texts).strip()
    resume_vision(gigi)

    name = extract_name(spoken_name, conversation=getattr(gigi, "conversation", None))
    print(f"[MakeFriends] Extracted name: '{name}' (from '{spoken_name}')")

    # 3. Display face crop on screen
    display_captured_face(gigi, face_crop, name)

    # 4. Confirm verification
    verified = False
    verification_attempts = 0
    while not verified and verification_attempts < 2:
        gigi.run_character(
            viseme_data={'text': f"Did I get your name right, {name}? Give me a thumbs up or say yes!", 'file': None},
            movement_data='nod'
        )

        res = verify_name_step(gigi, timeout=8.0)
        if res == "yes":
            verified = True
            break
        elif res == "no":
            gigi.run_character(
                viseme_data={'text': "Oops! Let's try spelling it out loud, letter by letter.", 'file': None}
            )
            pause_vision(gigi)
            gigi.hearing.texts = []
            gigi.listen_backchannel(timeout=8)
            spelled_text = " ".join(gigi.hearing.texts).strip()
            resume_vision(gigi)

            if spelled_text and hasattr(gigi, "conversation") and gigi.conversation:
                system_prompt = (
                    "You are a name extraction assistant. The user is spelling out their name. "
                    "Convert the spelled-out input into a single clean name (e.g. 'Goren'). "
                    "Output ONLY the extracted name."
                )
                reconstructed = gigi.conversation.get_response(system_prompt=system_prompt, user_prompt=spelled_text)
                name = reconstructed.strip().replace(".", "").replace("!", "").capitalize()
            verification_attempts += 1
        else:
            verification_attempts += 1

    if not verified:
        print("[MakeFriends] Name verification timed out or unconfirmed. Using 'Friend'.")
        name = "Friend"

    # 5. Voice profile enrollment
    gigi.run_character(
        viseme_data={'text': f"Great, {name}! Now, let's register your voice. Please repeat after me: Hello Gigi!", 'file': None},
        movement_data='home'
    )

    pause_vision(gigi)
    gigi.hearing.texts = []
    gigi.listen_backchannel(timeout=6)
    resume_vision(gigi)

    # 6. Save face and speaker updates
    try:
        if face_encoding is not None and hasattr(gigi, "vision") and hasattr(gigi.vision, "face_db"):
            gigi.vision.face_db.save_face_to_db(name, face_encoding)
            print(f"[MakeFriends] Saved face encoding for {name}.")
    except Exception as e:
        print(f"[MakeFriends] Error saving face encoding: {e}")

    try:
        speaker_db = SpeakerDatabase()
        if hasattr(gigi.hearing, "get_full_audio"):
            raw_audio = gigi.hearing.get_full_audio()
            if raw_audio is not None and len(raw_audio) >= 16000:
                from gigi.perception.speaker_id import VoiceEncoderRKNN
                encoder = VoiceEncoderRKNN()
                embedding = encoder.embed_utterance(raw_audio)
                speaker_db.add_speaker(name, embedding)
                print(f"[MakeFriends] Enrolled voice profile for {name}.")
    except Exception as e:
        print(f"[MakeFriends] Voice enrollment note: {e}")

    # Restore default face
    if hasattr(gigi, "face") and gigi.face:
        gigi.face.overlay_text = None
        gigi.face.run_sequence('idle')

    gigi.run_character(
        viseme_data={'text': f"Awesome! It's so nice to meet you, {name}!", 'file': None},
        movement_data='nod'
    )
    return True


def play_make_friends():
    """Standalone entry point for Make Friends social activity."""
    print("====================================================")
    print("             GIGI Make Friends Demo                 ")
    print("====================================================")

    gigi = Character(wakeup=True, activity="MakeFriends")
    time.sleep(1.0)

    try:
        if hasattr(gigi, "vision") and gigi.vision:
            gigi.vision.run_vision()
            time.sleep(1.0)

        gigi.run_character(
            viseme_data={'text': "Hi there! I want to meet some new friends. Let me look around!", 'file': None},
            movement_data='look_from_side_to_side'
        )
        gigi.run_character(movement_data='home')

        # Scan for faces
        all_faces = gigi.vision.face_cache.get_all_faces() if (hasattr(gigi, "vision") and gigi.vision) else {}
        for face_id, face_info in all_faces.items():
            name = face_info.get('name', 'Unknown')
            if name == 'Unknown' or re.match(r'^face_\d{4}$', name):
                register_new_friend(gigi, face_id)
                break
            else:
                gigi.run_character(
                    viseme_data={'text': f"Hello {name}! It is wonderful to see you again!", 'file': None},
                    face_data={'sequence': 'smile'}
                )
    except Exception as e:
        print(f"[MakeFriends] Activity error: {e}")
    finally:
        if hasattr(gigi, "vision") and gigi.vision:
            gigi.vision.stop_vision()
        gigi.stop_character()
        print("[MakeFriends] Demo finished.")


if __name__ == "__main__":
    play_make_friends()
