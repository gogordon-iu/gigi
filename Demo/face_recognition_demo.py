import os
import sys
import time
import random
import signal
import threading
import re
import csv

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
characterDefinitions.HAS_SPEECH = False
characterDefinitions.HAS_VISEME = False
characterDefinitions.HAS_CONVERSATION = False

from character import Character

def main():
    print("====================================================")
    print("           GIGI: Face Recognition Demo               ")
    print("====================================================")
    
    # Initialize character with wakeup=True to enable startup look/position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="Face Recognition Demo")
    gigi.face.overlay_text = None
    time.sleep(2)  # Allow motors and modules to initialize
    
    # Enable camera feed overlay on Gigi's screen
    gigi.show_camera_feed = True
    if gigi.face:
        gigi.face.show_camera_feed = True
        gigi.face.overlay_text = "Starting Face Recognition..."
        
    # State tracking variables
    running = True
    stop_event = threading.Event()
    start_time = time.time()
    
    # Set up log file
    log_dir = os.path.abspath(os.path.join(parent_dir, "logs"))
    os.makedirs(log_dir, exist_ok=True)
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_dir, f"face_rec_log_{timestamp_str}.csv")
    
    print(f"[Face Rec Demo] Logging details to: {log_file_path}")
    
    # Write CSV Header
    with open(log_file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Timestamp", "ElapsedSeconds", "FaceID", "X_Center", "Y_Center", "Box", "AssignedName", "IsNew", "ClosestMatchName", "ClosestDistance"])
    
    # Define signal handler for graceful exit (e.g. from SIGTERM / BT app stop command)
    def handle_signal(signum, frame):
        nonlocal running
        print(f"[Face Rec Demo] Received stop signal {signum}. Exiting cleanly...")
        running = False
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Start background vision system to track/recognize faces
        if gigi.vision:
            print("[Face Rec Demo] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        print("[Face Rec Demo] Entering face recognition loop. Press Ctrl+C or send STOP to exit.")
        
        last_log_print_time = 0.0
        last_debug_print_time = 0.0
        
        while running:
            # Diagnostic print
            if time.time() - last_debug_print_time > 2.0:
                is_running = gigi.vision.running if gigi.vision else False
                has_frame = gigi.vision.get_latest_frame() is not None if gigi.vision else False
                print(f"[Debug] vision.running={is_running}, latest_frame={'Not None' if has_frame else 'None'}, show_camera_feed={gigi.show_camera_feed}")
                last_debug_print_time = time.time()

            # Check for detected/tracked faces
            faces_detected = []
            if gigi.vision and gigi.vision.running:
                last_data = gigi.vision.get_last_data()
                current_time = time.time()
                
                for fid, face_info in last_data.items():
                    # Check if face was seen recently (within last 1.5 seconds)
                    last_seen_age = current_time - face_info.get('last_seen', 0)
                    if last_seen_age < 1.5:
                        faces_detected.append((fid, face_info))
            
            # Log and display detected faces
            if faces_detected:
                log_entries = []
                overlay_lines = [f"Detecting: Yes ({len(faces_detected)} face(s))"]
                
                # Open CSV file to append
                with open(log_file_path, "a", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    elapsed_time = time.time() - start_time
                    
                    for fid, info in faces_detected:
                        name = info.get('name', 'Unknown')
                        is_new = info.get('is_new', True)
                        closest_name = info.get('closest_name', 'None')
                        closest_dist = info.get('closest_dist', 1.0)
                        x = info.get('x', 0)
                        y = info.get('y', 0)
                        box = info.get('box', (0,0,0,0))
                        
                        # Log to CSV
                        writer.writerow([
                            current_time_str,
                            f"{elapsed_time:.2f}",
                            fid,
                            x,
                            y,
                            str(box),
                            name,
                            is_new,
                            closest_name,
                            f"{closest_dist:.4f}"
                        ])
                        
                        # Add details for screen overlay and terminal output
                        safe_name = name.encode('ascii', errors='ignore').decode()
                        safe_closest = closest_name.encode('ascii', errors='ignore').decode()
                        
                        overlay_lines.append(f"ID {fid}: {safe_name}")
                        overlay_lines.append(f"  Closest: {safe_closest} ({closest_dist:.2f})")
                        
                        log_entries.append(f"FaceID {fid} -> Assigned: '{safe_name}' | Closest DB Match: '{safe_closest}' (dist: {closest_dist:.4f})")
                
                # Periodically print to console (every 1 second) to avoid spamming stdout
                if time.time() - last_log_print_time > 1.0:
                    print(f"\n[Face Rec Demo] --- Timestamp: {time.strftime('%H:%M:%S')} ---")
                    for entry in log_entries:
                        print(f"  {entry}")
                    last_log_print_time = time.time()
                
                # Update screen overlay
                if gigi.face:
                    gigi.face.overlay_text = "\n".join(overlay_lines[:6]) # limit size to fit screen
            else:
                # No faces detected
                if gigi.face:
                    gigi.face.overlay_text = "Detecting: No\nNo faces in view."
                if time.time() - last_log_print_time > 2.0:
                    print("[Face Rec Demo] Scanning... No faces in view.")
                    last_log_print_time = time.time()
            
            # Sleep a bit while keeping the OpenCV window render loop alive
            if gigi.face and gigi.face.IMAGE_OPTION == "cv":
                gigi._cv_wait(0.1)
            else:
                time.sleep(0.1)
            
    except Exception as e:
        print(f"[Face Rec Demo] Error in main loop: {e}")
        
    finally:
        print("[Face Rec Demo] Performing clean up...")
        if gigi.vision:
            gigi.vision.stop_vision()
        if gigi.movement:
            print("[Face Rec Demo] Moving motors back to home position...")
            gigi.movement.home_position()
        gigi.stop_character()
        print(f"[Face Rec Demo] Finished. Saved run log to: {log_file_path}")

if __name__ == "__main__":
    main()
