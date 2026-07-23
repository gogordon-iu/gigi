import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = current_dir
char_dir = os.path.join(gigi_dir, "Character")

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)
if char_dir not in sys.path:
    sys.path.append(char_dir)

from Character.character import Character

def test_run():
    print("Initializing Character (fuzzy)...")
    gigi = Character(character_name="fuzzy", wakeup=True, full_screen=False)
    time.sleep(2.0)

    print("\n--- Test 1: Testing listen_fluid with Vision ---")
    print("Calling listen_fluid for 12 seconds. Face the camera so it centers your face.")
    gigi.listen_fluid(timeout=12, n_transcripts=1, run_speaker_recognition=False)
    print("\n--- Test 1 Completed ---")
    
    print("\n--- Test 2: Testing listen_backchannel with Vision ---")
    print("Calling listen_backchannel for 12 seconds. Speak and verify tracking & ear icon.")
    if gigi.vision and gigi.vision.running:
        print("Stopping vision to test auto-start in listen_backchannel...")
        gigi.vision.stop_vision()
        time.sleep(1.0)
        
    gigi.listen_backchannel(timeout=12)
    print("\n--- Test 2 Completed ---")

    print("\n--- Test 3: Testing register_new_friend Subroutine (thumbs_up & voice enrollment) ---")
    print("Setting up a mock face in face_cache...")
    if gigi.vision:
        if not gigi.vision.running:
            gigi.vision.run_vision()
        # Explicitly populate the faces dict with integer ID 1
        gigi.vision.face_cache.faces[1] = {
            'x': 200,
            'y': 200,
            'position_key': '200_200',
            'box': [100, 100, 300, 300],
            'name': 'Unknown',
            'emotion': 'Unknown',
            'gesture': 'Unknown',
            'last_recognition': 0,
            'last_emotion': 0,
            'last_seen': time.time(),
            'recognition_attempted': False,
            'is_new': True
        }
        gigi.vision.face_cache.position_to_face['200_200'] = 1
        
        import face_recognition
        face_recognition.face_encodings = lambda *args, **kwargs: [ [0.0]*128 ]
        
        from Demo.make_friends import register_new_friend
        
        print("\n*** INSTRUCTIONS ***")
        print("1. When asked for name: Say your name.")
        print("2. When asked to confirm: Give a clear thumbs-up to confirm (camera feed should show on screen).")
        print("3. When asked for favorite toy/animal: Speak into mic (camera feed and ear icon should show).")
        print("*********************\n")
        
        register_new_friend(gigi, face_id="1")
        print("\n--- Test 3 Completed ---")

    print("Cleaning up...")
    if gigi.vision and gigi.vision.running:
        gigi.vision.stop_vision()
    if gigi.face:
        gigi.face.stop_face()
    print("Test finished successfully!")

if __name__ == "__main__":
    test_run()
