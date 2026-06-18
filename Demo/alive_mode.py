import os
import sys
import time
import random
import signal
import threading

# Append the necessary paths to import Character modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)

character_dir = os.path.join(parent_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

from character import Character
from characterDefinitions import IS_ROBOT


def main():
    print("====================================================")
    print("            GIGI Showcase: Alive Mode               ")
    print("====================================================")
    
    # Initialize character with wakeup=True to enable startup look/position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="Showcase Alive")
    gigi.face.overlay_text = None
    time.sleep(2)  # Allow motors and modules to initialize
    
    # State tracking variables
    running = True
    stop_event = threading.Event()
    allow_track = True
    
    # Define signal handler for graceful exit (e.g. from SIGTERM / BT app stop command)
    def handle_signal(signum, frame):
        nonlocal running
        print(f"[Alive Mode] Received signal {signum}. Exiting cleanly...")
        running = False
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Start background vision system to track faces
        if gigi.vision:
            print("[Alive Mode] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # Initial greeting
        print("[Alive Mode] Playing initial greeting...")
        gigi.run_character(
            viseme_data={'text': "Hello everyone! I am Gigi. It is wonderful to meet you today!", 'file': None},
            movement_data='wave_hello'
        )
        
        # Keep arms down after greeting
        print("[Alive Mode] Lowering arms...")
        gigi.run_character(movement_data='arms_down')
        
        last_shift_time = time.time()
        last_look_around_time = time.time()
        next_blink_time = time.time() + random.uniform(3.0, 6.0)
        
        print("[Alive Mode] Entering main loop. Press Ctrl+C or send stop signal to exit.")
        while running:
            # 1. Periodic blinking
            if time.time() >= next_blink_time:
                # Run the blink sequence on the face
                gigi.face.run_sequence("blink")
                next_blink_time = time.time() + random.uniform(3.0, 6.0)
                
            # 2. Periodic subtle body shift/movement (every 15 to 25 seconds) using new smooth sequences
            if time.time() - last_shift_time > random.uniform(15.0, 25.0):
                shift_seq = random.choice(["alive_shift", "alive_look_around", "alive_gently_look_left", "alive_gently_look_right"])
                print(f"[Alive Mode] Executing smooth movement: {shift_seq}")
                gigi.run_character(movement_data=shift_seq)
                last_shift_time = time.time()
                # Push back other timers to avoid overlapping animations
                last_look_around_time = time.time()
                next_blink_time = time.time() + random.uniform(4.0, 7.0)
                
            # 3. Smooth looking around or face tracking (every 8 to 15 seconds)
            if time.time() - last_look_around_time > random.uniform(8.0, 15.0):
                face_seen = False
                if gigi.vision and gigi.vision.running:
                    last_data = gigi.vision.get_last_data()
                    # If we have a face detected in the last 2 seconds
                    face_seen = len(last_data) > 0 and (time.time() - next(iter(last_data.values())).get('last_seen', 0) < 2.0)
                
                if face_seen and allow_track:
                    print("[Alive Mode] Face detected! Following face smoothly...")
                    # Track face for 5 seconds, then go to panning
                    gigi.follow_face(timeout=5.0, stop_event=stop_event)
                    allow_track = False  # Next cycle is forced to pan
                else:
                    print("[Alive Mode] Smoothly looking around...")
                    # Smooth motor pan
                    target_torso = random.uniform(-0.25, 0.25)
                    target_neck = random.uniform(-0.15, 0.15)
                    if gigi.movement:
                        gigi.movement.move_motors({"torso": target_torso, "neck": target_neck})
                        
                    # Eye look direction
                    eye_seq = random.choice(["look_left", "look_right", "look_up", "look_down"])
                    gigi.face.run_sequence(eye_seq)
                    
                    # Pause for a bit while looking in that direction
                    look_start = time.time()
                    while running and (time.time() - look_start < 1.5):
                        time.sleep(0.1)
                    
                    # Return eyes to center
                    gigi.face.run_sequence("idle")
                    allow_track = True  # Panning finished, allow face-tracking next time
                    
                last_look_around_time = time.time()
                
            # Sleep a bit to prevent high CPU usage
            time.sleep(0.1)
            
    except Exception as e:
        print(f"[Alive Mode] Error in main loop: {e}")
        
    finally:
        print("[Alive Mode] Performing clean up...")
        if gigi.vision:
            gigi.vision.stop_vision()
        if gigi.movement:
            print("[Alive Mode] Moving motors back to home position...")
            gigi.movement.home_position()
        gigi.stop_character()
        print("[Alive Mode] Gigi has finished cleanly.")

if __name__ == "__main__":
    main()
