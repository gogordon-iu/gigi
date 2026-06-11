import os
import sys
import time
import re
import cv2
import threading
import numpy as np

# Append parent dir, Character dir, and Demo dir to path
current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(current_dir)

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)

character_dir = os.path.join(gigi_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

if current_dir not in sys.path:
    sys.path.append(current_dir)

from character import Character
from capabilities import extract_name
from make_friends import SpeakerDatabase

def pause_vision(gigi):
    """Temporarily pause vision processing to optimize STT performance."""
    if gigi.vision:
        print("[Subroutine] Pausing vision processing for speech listening...")
        gigi.vision.set_processing_flags({
            'face_detection': 0,
            'face_recognition': 0,
            'emotion': 0,
            'gesture': 0
        })
        time.sleep(0.2)

def resume_vision(gigi):
    """Resume vision processing after pause."""
    if gigi.vision:
        print("[Subroutine] Resuming vision processing...")
        gigi.vision.set_processing_flags({
            'face_detection': 8.0,
            'face_recognition': 8.0,
            'emotion': 0,
            'gesture': 8.0
        })
        time.sleep(0.2)

def display_captured_face(gigi, face_crop, name):
    """Displays the captured face of the child on Gigi's screen with their name written below it."""
    if not gigi.face:
        return
        
    gigi.face.overlay_text = name
    
    if gigi.face.IMAGE_OPTION == "pygame":
        import pygame
        # Convert BGR (OpenCV) to RGB (Pygame)
        rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        h, w = rgb_crop.shape[:2]
        pg_surface = pygame.image.fromstring(rgb_crop.tobytes(), (w, h), "RGB")
        gigi.face.display_face(pg_surface)
    elif gigi.face.IMAGE_OPTION == "cv":
        gigi.face.display_face(face_crop)
    print(f"[Subroutine] Displaying face crop for '{name}' on screen.")

def verify_name_step(gigi, timeout=10.0):
    """
    Concurrent verification subroutine.
    Checks for Thumbs Up / Thumbs Down gesture in background thread while
    verbally listening for affirmation (yes/no) in main thread.
    """
    gesture_result = [None]  # None, "yes", "no"
    stop_gesture_thread = threading.Event()
    
    def gesture_poller():
        start_t = time.time()
        while not stop_gesture_thread.is_set() and (time.time() - start_t < timeout):
            if gigi.vision:
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
    if gigi.hearing:
        gigi.hearing.texts = []
        gigi.listen_backchannel(timeout=timeout)
        heard = " ".join(gigi.hearing.texts).lower().strip()
        print(f"[Verification] Heard: '{heard}'")
        
        # Check for yes/no patterns
        yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's me", "uh-huh"]
        no_patterns = ["no", "nope", "incorrect", "wrong", "that's not me", "uh-uh"]
        
        if any(w in heard for w in yes_patterns):
            verbal_result = "yes"
        elif any(w in heard for w in no_patterns):
            verbal_result = "no"
            
    # Stop background thread and join
    stop_gesture_thread.set()
    t.join(timeout=1.0)
    
    # Gesture takes priority if recognized, otherwise verbal
    if gesture_result[0] is not None:
        return gesture_result[0]
    return verbal_result

def register_new_friend(gigi, face_id):
    """
    Subroutine to register a new unknown face:
    1. Captures child's face crop and encoding.
    2. Asks child's name and extracts it.
    3. Displays child's face on screen and overlays the name.
    4. Asks child to verify verbally or via thumbs up.
    5. If incorrect, asks child to spell name, reconstructs it using LLM, and re-verifies.
    6. Once confirmed, captures voice/speaker enrollment and saves both profiles to databases.
    """
    print(f"\n[Subroutine] Starting registration process for face_id: {face_id}")
    
    import face_recognition
    
    # 1. Capture face crop and face encoding
    frame = gigi.vision.get_latest_frame() if gigi.vision else None
    if frame is None:
        print("[Subroutine] Error: Camera frame not available.")
        return False
        
    face_data = gigi.vision.face_cache.get_face_data(face_id)
    if not face_data or 'box' not in face_data:
        print(f"[Subroutine] Error: Face data not found for ID: {face_id}")
        return False
        
    x_min, y_min, x_max, y_max = face_data['box']
    h_f, w_f = frame.shape[:2]
    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(w_f, x_max)
    y_max = min(h_f, y_max)
    
    face_crop = frame[y_min:y_max, x_min:x_max]
    if face_crop.size == 0:
        print("[Subroutine] Error: Invalid face crop dimensions.")
        return False
        
    # Extract encoding
    small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
    face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
    face_encodings = face_recognition.face_encodings(face_crop_rgb)
    if not face_encodings:
        print("[Subroutine] Error: Could not extract face encoding.")
        return False
    face_encoding = face_encodings[0]
    
    # 2. Ask child's name
    gigi.run_character(
        viseme_data={'text': "Hi! I don't think we've met. What is your name?", 'file': None},
        movement_data='open_arms'
    )
    
    pause_vision(gigi)
    gigi.hearing.texts = []
    gigi.listen_backchannel(timeout=8)
    heard_name = " ".join(gigi.hearing.texts).strip()
    resume_vision(gigi)
    
    name = extract_name(heard_name, gigi=gigi)
    print(f"[Subroutine] Extracted Name: {name}")
    
    # 3. Display face crop and write name
    display_captured_face(gigi, face_crop, name)
    
    # 4. Verification loop
    verified = False
    verification_attempts = 0
    
    while not verified and verification_attempts < 3:
        gigi.run_character(
            viseme_data={'text': "Is that you, and did I spell your name correctly? Give me a thumbs up or say yes or no.", 'file': None}
        )
        
        # Concurrent verify check
        result = verify_name_step(gigi, timeout=10.0)
        print(f"[Subroutine] Verification check result: {result}")
        
        if result == "yes":
            verified = True
            break
        elif result == "no":
            # Ask child to spell out their name
            gigi.run_character(
                viseme_data={'text': "Oh, I'm sorry! Can you please spell out your name for me, letter by letter?", 'file': None}
            )
            
            pause_vision(gigi)
            gigi.hearing.texts = []
            gigi.listen_backchannel(timeout=10)
            spelled_text = " ".join(gigi.hearing.texts).strip()
            resume_vision(gigi)
            
            if spelled_text:
                system_prompt = (
                    "You are a name extraction assistant. The user is spelling out their name. "
                    "Convert the spelled-out input (e.g. 'G O R E N', 'G as in George, O, R, E, N') "
                    "into a single, clean, properly capitalized name (e.g. 'Goren'). "
                    "Output ONLY the extracted name, nothing else."
                )
                reconstructed = gigi.conversation.get_response(system_prompt=system_prompt, user_prompt=spelled_text)
                name = reconstructed.strip().replace(".", "").replace("!", "")
                # Enforce single word
                if len(name.split()) > 1:
                    name = name.split()[0]
                print(f"[Subroutine] Reconstructed name from spelling: '{name}'")
            else:
                name = "Friend"
                
            # Update display with reconstructed name
            display_captured_face(gigi, face_crop, name)
            verification_attempts += 1
        else:
            gigi.run_character(
                viseme_data={'text': "I didn't catch a gesture or response. Let's try confirming again.", 'file': None}
            )
            verification_attempts += 1
            
    if not verified:
        print("[Subroutine] Verification failed.")
        # Restore default face
        gigi.face.overlay_text = None
        gigi.face.display_text(None)
        gigi.face.run_sequence('idle')
        gigi.run_character(
            viseme_data={'text': "I'm having some trouble confirming your name. Let's try again later!", 'file': None}
        )
        return False
        
    # 5. Capture speaker recognition / voice enrollment
    gigi.run_character(
        viseme_data={'text': f"Great, {name}! Now, let's register your voice. Please repeat after me: The quick brown fox jumps over the lazy dog.", 'file': None},
        movement_data='open_arms'
    )
    
    pause_vision(gigi)
    gigi.hearing.texts = []
    gigi.listen_backchannel(timeout=10)
    raw_audio = gigi.hearing.get_full_audio()
    resume_vision(gigi)
    
    speaker_embedding = None
    if raw_audio is not None and len(raw_audio) >= 16000:
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
            print("[Subroutine] Extracting speaker embedding...")
            encoder = VoiceEncoder()
            wav = preprocess_wav(raw_audio)
            speaker_embedding = encoder.embed_utterance(wav)
            print("[Subroutine] Voice profile enrollment successful.")
        except Exception as e:
            print(f"[Subroutine] Error during voice extraction: {e}")
            
    # 6. Save both face & speaker updates to database files
    print("[Subroutine] Saving face encoding to database...")
    try:
        gigi.vision.face_db.save_face_to_db(name, face_encoding)
        print("[Subroutine] Face encoding saved successfully.")
    except Exception as e:
        print(f"[Subroutine] Error saving face encoding: {e}")
        
    if speaker_embedding is not None:
        print("[Subroutine] Saving speaker embedding to database...")
        try:
            speaker_db = SpeakerDatabase()
            speaker_db.add_speaker(name, speaker_embedding)
            print("[Subroutine] Speaker profile saved successfully.")
        except Exception as e:
            print(f"[Subroutine] Error saving speaker profile: {e}")
    else:
        print("[Subroutine] Warning: Speaker profile was not enrolled.")
        
    # Restore normal face/screen
    gigi.face.overlay_text = None
    gigi.face.display_text(None)
    gigi.face.run_sequence('idle')
    
    # Celebrate
    gigi.run_character(
        viseme_data={'text': f"Awesome! I've saved your face and voice. It's so nice to meet you, {name}!", 'file': None},
        movement_data='clap'
    )
    return True

def play_make_friends():
    print("====================================================")
    print("             GIGI Make Friends Demo                 ")
    print("====================================================")
    
    gigi = Character(character_name="fuzzy", wakeup=True, activity="MakeFriends")
    time.sleep(2)
    
    try:
        if gigi.vision:
            print("[Demo] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        gigi.run_character(
            viseme_data={'text': "Hi there! I want to meet some new friends. Let me look around!", 'file': None},
            movement_data='look_from_side_to_side'
        )
        gigi.run_character(movement_data='home')
        
        unknown_faces_timers = {}
        timeout_wait = 3.0  # Confirmed unknown for 3 seconds
        
        demo_active = True
        while demo_active:
            all_faces = gigi.vision.face_cache.get_all_faces() if gigi.vision else {}
            
            if not all_faces:
                print("Scanning for faces...", end='\r')
                time.sleep(0.5)
                continue
                
            current_unknown_ids = set()
            known_greeted = set()
            
            for face_id, face_info in all_faces.items():
                name = face_info.get('name', 'Unknown')
                is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                is_unknown = (name == 'Unknown' or is_face_pattern or (name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
                
                if not is_unknown and name != 'Recognizing...':
                    if name not in known_greeted:
                        print(f"\n[Demo] Recognized known face: '{name}'")
                        gigi.run_character(
                            viseme_data={'text': f"Hello {name}! It is wonderful to see you again!", 'file': None},
                            face_data={'sequence': 'smile'}
                        )
                        known_greeted.add(name)
                        time.sleep(3.0)
                else:
                    current_unknown_ids.add(face_id)
                    if face_id not in unknown_faces_timers:
                        unknown_faces_timers[face_id] = time.time()
                        print(f"\n[Demo] Detected unknown face (ID: {face_id}). Confirming...")
                        
                    elapsed = time.time() - unknown_faces_timers[face_id]
                    if elapsed >= timeout_wait:
                        print(f"\n[Demo] Confirmed unknown face (ID: {face_id}). Launching registration subroutine...")
                        
                        # Stop scanning during registration process
                        gigi.vision.stop_vision()
                        time.sleep(0.5)
                        
                        success = register_new_friend(gigi, face_id)
                        
                        if success:
                            demo_active = False  # End demo on success
                            break
                        else:
                            # Resume vision and clean up timers on failure
                            if gigi.vision:
                                gigi.vision.run_vision()
                            unknown_faces_timers.clear()
                            break
                            
            # Clean up old timers
            to_remove = [fid for fid in unknown_faces_timers if fid not in current_unknown_ids]
            for fid in to_remove:
                del unknown_faces_timers[fid]
                
            time.sleep(0.2)
            
    except Exception as e:
        print(f"[Demo] Error: {e}")
    finally:
        if gigi.vision:
            gigi.vision.stop_vision()
        gigi.stop_character()
        print("[Demo] Make Friends Demo finished.")

if __name__ == "__main__":
    play_make_friends()
