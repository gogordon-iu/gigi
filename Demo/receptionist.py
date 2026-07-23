import os
import sys
import time
import random
import signal
import threading
import re

# Append the necessary paths to import Character modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)

character_dir = os.path.join(parent_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

# Speed up startup by disabling unused modules
import characterDefinitions
characterDefinitions.HAS_HEARING = False
characterDefinitions.HAS_CONVERSATION = False

from character import Character

def main():
    print("====================================================")
    print("           GIGI Showcase: Receptionist Mode          ")
    print("====================================================")
    
    # Initialize character with wakeup=True to enable startup look/position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="Showcase Receptionist")
    gigi.show_camera_feed = True
    if gigi.face:
        gigi.face.show_camera_feed = True
        gigi.face.overlay_text = None
    time.sleep(2)  # Allow motors and modules to initialize
    
    # State tracking variables
    running = True
    stop_event = threading.Event()
    allow_track = True
    start_time = time.time()
    
    # Cooldown tracking for recognized people (key: name, value: last_greeted_timestamp)
    last_greeted = {}
    
    # Define signal handler for graceful exit (e.g. from SIGTERM / BT app stop command)
    def handle_signal(signum, frame):
        nonlocal running
        print(f"[Receptionist Mode] Received signal {signum}. Exiting cleanly...")
        running = False
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Start background vision system to track/recognize faces
        if gigi.vision:
            print("[Receptionist Mode] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # Initial greeting
        print("[Receptionist Mode] Playing initial welcome...")
        gigi.run_character(
            viseme_data={'text': "Hello everyone! I am Gigi, and I will be your receptionist today.", 'file': None},
            movement_data='wave_hello'
        )
        
        # Keep arms down after greeting
        print("[Receptionist Mode] Lowering arms...")
        gigi.run_character(movement_data='arms_down')
        
        last_shift_time = time.time()
        last_look_around_time = time.time()
        next_blink_time = time.time() + random.uniform(3.0, 6.0)
        
        print("[Receptionist Mode] Entering main loop. Greet loop will run up to 20 minutes or until STOP signal.")
        while running:
            # 1. Check elapsed time (20 minutes = 1200 seconds)
            elapsed = time.time() - start_time
            if elapsed > 1200:
                print("[Receptionist Mode] 20 minutes elapsed. Shutting down receptionist...")
                running = False
                break
                
            # 2. Debugging: Check face detection status and closest recognized face
            face_detected_now = False
            closest_name_debug = "None"
            closest_dist_debug = 1.0
            
            # Check for recognized face with high confidence (for greeting)
            recognized_name = None
            if gigi.vision and gigi.vision.running:
                last_data = gigi.vision.get_last_data()
                for fid, face_info in last_data.items():
                    # Ensure face was seen very recently (within last 1.5 seconds)
                    if time.time() - face_info.get('last_seen', 0) < 1.5:
                        face_detected_now = True
                        c_name = face_info.get('closest_name', 'None')
                        c_dist = face_info.get('closest_dist', 1.0)
                        if c_name != 'None':
                            if closest_name_debug == "None" or c_dist < closest_dist_debug:
                                closest_name_debug = c_name
                                closest_dist_debug = c_dist
                                
                        name = face_info.get('name', 'Unknown')
                        is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                        is_unknown = (name == 'Unknown' or is_face_pattern or name == 'Recognizing...')
                        
                        if not is_unknown:
                            # Apply 45-second cooldown per person to avoid repetitive greetings
                            if time.time() - last_greeted.get(name, 0) > 45.0:
                                recognized_name = name
                                # Do not break immediately so we can scan all faces for closest name/distance logging
            
            # Update debugging overlay text
            if gigi.face:
                gigi.face.overlay_text = f"Face Detected: {'Yes' if face_detected_now else 'No'}\nClosest: {closest_name_debug} (dist: {closest_dist_debug:.3f})"
            
            # 3. If a face is recognized, perform the receptionist greeting
            if recognized_name:
                print(f"[Receptionist Mode] Recognized: {recognized_name}. Greeting...")
                last_greeted[recognized_name] = time.time()
                
                # Ensure the name is present in egocentric_db so run_character gaze redirection matches it
                if recognized_name not in gigi.egocentric_db:
                    gigi.egocentric_db[recognized_name] = {"angle": 0.0, "timestamp": time.time()}
                
                # Update text on the bottom
                greeting_text = f"Hi {recognized_name}. It's great to see you"
                gigi.face.overlay_text = greeting_text
                
                # Say it and wave hello (automatically redirects gaze to person)
                gigi.run_character(
                    viseme_data={'text': greeting_text, 'file': None},
                    movement_data='wave_hello'
                )
                
                # Lower arms back down
                gigi.run_character(movement_data='arms_down')
                
                # Keep text on screen for 3 more seconds, then clear it
                time.sleep(3.0)
                gigi.face.overlay_text = None
                
                # Reset idle timers to prevent immediate look-around shift right after greeting
                last_shift_time = time.time()
                last_look_around_time = time.time()
                next_blink_time = time.time() + random.uniform(4.0, 7.0)
                allow_track = False  # Force a panning look next cycle to show we are looking at others
                continue
                
            # 4. Periodic blinking (if not currently greeting)
            if time.time() >= next_blink_time:
                gigi.face.run_sequence("blink")
                next_blink_time = time.time() + random.uniform(3.0, 6.0)
                
            # 5. Periodic subtle shift/movement (every 15 to 25 seconds)
            if time.time() - last_shift_time > random.uniform(15.0, 25.0):
                shift_seq = random.choice(["alive_shift", "alive_look_around", "alive_gently_look_left", "alive_gently_look_right"])
                print(f"[Receptionist Mode] Executing subtle movement: {shift_seq}")
                gigi.run_character(movement_data=shift_seq)
                last_shift_time = time.time()
                last_look_around_time = time.time()
                next_blink_time = time.time() + random.uniform(4.0, 7.0)
                
            # 6. Periodic smooth looking around or face tracking (every 8 to 15 seconds)
            if time.time() - last_look_around_time > random.uniform(8.0, 15.0):
                face_seen = False
                if gigi.vision and gigi.vision.running:
                    last_data = gigi.vision.get_last_data()
                    face_seen = len(last_data) > 0 and (time.time() - next(iter(last_data.values())).get('last_seen', 0) < 2.0)
                
                if face_seen and allow_track:
                    print("[Receptionist Mode] Face detected. Following face smoothly...")
                    gigi.follow_face(timeout=5.0, stop_event=stop_event)
                    allow_track = False  # Next cycle is forced to pan
                else:
                    print("[Receptionist Mode] Smoothly looking around...")
                    target_torso = random.uniform(-0.25, 0.25)
                    target_neck = random.uniform(-0.15, 0.15)
                    if gigi.movement:
                        gigi.run_character(movement_data={"torso": target_torso, "neck": target_neck, "duration": 2.0})
                        
                    eye_seq = random.choice(["look_left", "look_right", "look_up", "look_down"])
                    gigi.face.run_sequence(eye_seq)
                    
                    look_start = time.time()
                    while running and (time.time() - look_start < 1.5):
                        if gigi.face and gigi.face.IMAGE_OPTION == "cv":
                            gigi._cv_wait(0.1)
                        else:
                            time.sleep(0.1)
                        
                    gigi.face.run_sequence("idle")
                    allow_track = True  # Allow face-tracking next time
                    
                last_look_around_time = time.time()
                
            # Sleep a bit while keeping the OpenCV window render loop alive
            if gigi.face and gigi.face.IMAGE_OPTION == "cv":
                gigi._cv_wait(0.1)
            else:
                time.sleep(0.1)
            
    except Exception as e:
        print(f"[Receptionist Mode] Error in main loop: {e}")
        
    finally:
        print("[Receptionist Mode] Performing clean up...")
        if gigi.vision:
            gigi.vision.stop_vision()
        if gigi.movement:
            print("[Receptionist Mode] Moving motors back to home position...")
            gigi.movement.home_position()
        gigi.stop_character()
        print("[Receptionist Mode] Receptionist demo finished cleanly.")

if __name__ == "__main__":
    main()
