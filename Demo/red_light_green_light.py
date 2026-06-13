import os
import sys
import time
import random
import re
import cv2
import threading
import numpy as np

# Setup pathing
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
from characterDefinitions import IS_ROBOT
from Demo.make_friends import register_new_friend

# Import predefined arm movements
try:
    from movementDefinition import basic_sequences
except ImportError:
    # Fallback to manual dictionary if not importable
    basic_sequences = {
        "arms_up": [
            {'time': 1.0, 'motors': {'right_elbow': 0.0, 'left_elbow': 0.0, 'right_shoulder': 0.8, 'left_shoulder': -0.8}}
        ],
        "arms_down": [
            {'time': 1.0, 'motors': {'right_elbow': 0.8, 'left_elbow': -0.8, 'right_shoulder': -0.8, 'left_shoulder': 0.8}}
        ],
        "home": [
            {'time': 1.0, 'motors': {'neck': 0.0, 'right_shoulder': 0.0, 'left_shoulder': 0.0, 'right_elbow': 0.0, 'left_elbow': 0.0, 'torso': 0.0}}
        ]
    }

def detect_motion_for_faces(gigi, duration=3.0, motion_threshold=1500, max_x_diff_ratio=0.15):
    """
    Monitors camera for motion during 'Red Light' phase.
    Tries to associate motion blobs with recognized faces based on the x-axis.
    Returns a set of names (or face IDs) of people who moved.
    """
    if not gigi.vision or not gigi.vision.running:
        # Simulation Mode
        print("\n[Simulation Mode - Motion Detector]")
        print("Did anyone move? Type name(s) of who moved (separated by commas), or press Enter for no movement:")
        try:
            resp = input("> ").strip()
            if not resp:
                return set()
            return {name.strip() for name in resp.split(",") if name.strip()}
        except (KeyboardInterrupt, EOFError):
            return set()

    start_time = time.time()
    moved_players = set()
    
    # Wait 0.5 seconds for Gigi's own motor moves (arms down, face update) to settle
    time.sleep(0.5)
    
    # Grab the baseline frame
    frame_base = gigi.vision.get_latest_frame()
    if frame_base is None:
        print("[Motion Detector] Warning: Could not retrieve baseline frame.")
        return set()
        
    h, w = frame_base.shape[:2]
    gray_base = cv2.cvtColor(frame_base, cv2.COLOR_BGR2GRAY)
    gray_base = cv2.GaussianBlur(gray_base, (21, 21), 0)
    
    # Dictionary to accumulate motion area per face_id
    motion_accumulation = {}
    loop_count = 0
    
    print("[Motion Detector] Monitoring started...")
    
    while time.time() - start_time < duration:
        frame_current = gigi.vision.get_latest_frame()
        if frame_current is None:
            time.sleep(0.1)
            continue
            
        gray_current = cv2.cvtColor(frame_current, cv2.COLOR_BGR2GRAY)
        gray_current = cv2.GaussianBlur(gray_current, (21, 21), 0)
        
        # Calculate absolute difference
        diff = cv2.absdiff(gray_base, gray_current)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        all_faces = gigi.vision.face_cache.get_all_faces()
        # Filter for faces seen recently (last 2 seconds)
        active_faces = {
            fid: data for fid, data in all_faces.items()
            if time.time() - data.get('last_seen', 0) < 2.0
        }
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 300:  # Ignore tiny speckles
                continue
                
            (x, y, cw, ch) = cv2.boundingRect(contour)
            contour_center_x = x + cw / 2.0
            
            # Find closest face by x-axis
            closest_face_id = None
            min_x_diff = w * max_x_diff_ratio
            
            for fid, face_data in active_faces.items():
                face_x = face_data['x']
                x_diff = abs(contour_center_x - face_x)
                if x_diff < min_x_diff:
                    min_x_diff = x_diff
                    closest_face_id = fid
                    
            if closest_face_id is not None:
                motion_accumulation[closest_face_id] = motion_accumulation.get(closest_face_id, 0) + area
                
        loop_count += 1
        time.sleep(0.1)
        
    print(f"[Motion Detector] Monitoring completed over {loop_count} frames.")
    
    # Check who exceeded the motion threshold
    for fid, total_area in motion_accumulation.items():
        # Normalize motion area by frame loops
        normalized_motion = total_area / max(loop_count, 1)
        print(f"[Motion Detector] Face {fid} normalized motion: {normalized_motion:.1f}")
        
        if normalized_motion > motion_threshold:
            face_data = gigi.vision.face_cache.get_face_data(fid)
            name = face_data.get('name', 'Unknown')
            if name in ['Unknown', 'Recognizing...']:
                name = f"Player {fid}"
            moved_players.add(name)
            
    return moved_players

def check_for_winner(gigi):
    """
    Checks if any player's face fills most of the camera view.
    Returns the name of the winning player, or None.
    """
    if not gigi.vision or not gigi.vision.running:
        # Simulation Mode
        print("\n[Simulation Mode - Winner Check]")
        print("Did anyone reach Gigi and win? Type name, or press Enter to continue:")
        try:
            resp = input("> ").strip()
            return resp if resp else None
        except (KeyboardInterrupt, EOFError):
            return None
            
    all_faces = gigi.vision.face_cache.get_all_faces()
    frame = gigi.vision.get_latest_frame()
    if frame is None or not all_faces:
        return None
        
    h, w = frame.shape[:2]
    frame_area = w * h
    
    for fid, face_data in all_faces.items():
        if time.time() - face_data.get('last_seen', 0) > 2.0:
            continue
            
        box = face_data.get('box')
        if not box:
            continue
            
        x_min, y_min, x_max, y_max = box
        face_w = x_max - x_min
        face_h = y_max - y_min
        face_area = face_w * face_h
        
        area_ratio = face_area / frame_area
        width_ratio = face_w / w
        
        # Face fills most of the camera:
        # Area ratio > 0.25 (25% of image) or Width ratio > 0.45 (45% of width)
        if area_ratio > 0.25 or width_ratio > 0.45:
            name = face_data.get('name', 'Unknown')
            if name in ['Unknown', 'Recognizing...']:
                name = f"Player {fid}"
            return name
            
    return None

def set_eyes_state(gigi, closed=True):
    """Manually commands Gigi's face to have closed eyes or normal open eyes."""
    if not gigi.face:
        return
        
    if closed:
        face_state = {"Eyes": ("blink", "5"), "Nose": ("idle", "1"), "Mouth": ("idle", "1")}
    else:
        face_state = {"Eyes": ("idle", "1"), "Nose": ("idle", "1"), "Mouth": ("idle", "1")}
        
    face_img = gigi.face.set_face(face_state)
    gigi.face.display_face(face_img)

def play_red_light_green_light():
    print("====================================================")
    print("         GIGI Red Light Green Light Game Demo        ")
    print("====================================================")
    
    gigi = Character(character_name="fuzzy", wakeup=True, activity="RedLightGreenLight")
    gigi.face.overlay_text = None
    time.sleep(2)
    
    try:
        if gigi.vision:
            print("[RLGL] Starting background vision system...")
            gigi.vision.run_vision()
            time.sleep(1.0)
            
        # 1. Startup & Recognition phase
        gigi.run_character(
            viseme_data={'text': "Hi everyone! Let's play Red Light Green Light! Look at me so I can see who is playing today.", 'file': None},
            movement_data='look_from_side_to_side'
        )
        if gigi.movement:
            gigi.movement.move_sequence(basic_sequences['home'])
            
        # Scan for players
        print("[RLGL] Scanning for players (5 seconds)...")
        time.sleep(5.0)
        
        all_faces = gigi.vision.face_cache.get_all_faces() if gigi.vision else {}
        current_faces = {fid: info for fid, info in all_faces.items() if time.time() - info.get('last_seen', 0) < 3.0}
        
        players = {} # face_id -> name
        
        if not current_faces and (not gigi.vision or not gigi.vision.running):
            # Simulation Mode startup
            print("\n[Simulation Mode] Who is playing? Enter names separated by commas:")
            try:
                names_input = input("> ").strip()
                if names_input:
                    for idx, name in enumerate(names_input.split(",")):
                        players[str(idx).zfill(4)] = name.strip()
                else:
                    players["0001"] = "Friend"
            except (KeyboardInterrupt, EOFError):
                players["0001"] = "Friend"
        else:
            # Greet recognized players and register new friends
            for fid, face_info in current_faces.items():
                name = face_info.get('name', 'Unknown')
                is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                is_unknown = (name == 'Unknown' or is_face_pattern or name == 'Recognizing...')
                
                if not is_unknown:
                    # Greet recognized player
                    gigi.run_character(
                        viseme_data={'text': f"Hello {name}! It is wonderful to play with you again!", 'file': None},
                        movement_data='wave_hello'
                    )
                    players[fid] = name
                    time.sleep(2.0)
                else:
                    # Make friends with unknown player
                    success = register_new_friend(gigi, fid)
                    if success:
                        updated_face = gigi.vision.face_cache.get_face_data(fid)
                        name = updated_face.get('name', f"Player {fid}")
                        players[fid] = name
                    else:
                        players[fid] = f"Player {fid}"
                        
        if not players:
            players["0001"] = "Friend"
            
        # 2. Setup Phase: Walk away
        names_list = ", ".join(players.values())
        gigi.run_character(
            viseme_data={'text': f"Awesome, we have {names_list} playing! Please walk away a little bit so you have space to run towards me!", 'file': None},
            movement_data='open_arms'
        )
        time.sleep(4.0)
        
        # Verify visibility of players
        if gigi.vision and gigi.vision.running:
            while True:
                faces = gigi.vision.face_cache.get_all_faces()
                active = {fid for fid, info in faces.items() if time.time() - info.get('last_seen', 0) < 2.0}
                if active:
                    break
                else:
                    gigi.run_character(
                        viseme_data={'text': "I can't see anyone! Please come closer or look at me.", 'file': None}
                    )
                    time.sleep(4.0)
                    
        gigi.run_character(
            viseme_data={'text': "Okay, I see you! Let's start! Remember, move when I say green light, and stop when I say red light!", 'file': None}
        )
        time.sleep(2.0)
        
        # 3. Game Loop
        game_active = True
        while game_active:
            # --- GREEN LIGHT ---
            print("\n[RLGL State] GREEN LIGHT")
            gigi.face.overlay_text = "GREEN LIGHT" if gigi.face else None
            set_eyes_state(gigi, closed=True)
            
            # Raise arms
            if gigi.movement:
                gigi.movement.move_sequence(basic_sequences['arms_up'])
                
            # Roll random duration 2-5s
            green_duration = random.uniform(2.0, 5.0)
            print(f"[RLGL] Waiting green light for {green_duration:.2f} seconds...")
            
            # Speak Green Light
            gigi.run_character(
                viseme_data={'text': "Green Light!", 'file': None}
            )
            time.sleep(green_duration)
            
            # --- RED LIGHT ---
            print("\n[RLGL State] RED LIGHT")
            gigi.face.overlay_text = "RED LIGHT" if gigi.face else None
            set_eyes_state(gigi, closed=False)
            
            # Move arms down
            if gigi.movement:
                gigi.movement.move_sequence(basic_sequences['arms_down'])
                
            gigi.run_character(
                viseme_data={'text': "Red Light!", 'file': None}
            )
            
            # Run motion detection during red light (lasts 2.5s)
            moved_players = detect_motion_for_faces(gigi, duration=2.5)
            
            if moved_players:
                # Tell players who moved to step back
                for name in moved_players:
                    gigi.run_character(
                        viseme_data={'text': f"{name}, I saw you moved! Three steps back!", 'file': None},
                        movement_data='look_from_side_to_side'
                    )
                    time.sleep(2.0)
            else:
                # No one moved! Check for winner
                winner = check_for_winner(gigi)
                if winner:
                    # Winner celebration!
                    gigi.face.overlay_text = "WINNER!" if gigi.face else None
                    gigi.run_character(
                        viseme_data={'text': f"Wow! Congratulations, {winner}! You reached me and won the game!", 'file': None},
                        movement_data='clap'
                    )
                    if gigi.face:
                        gigi.face.run_sequence('smile')
                    time.sleep(4.0)
                    game_active = False
                else:
                    gigi.run_character(
                        viseme_data={'text': "Good job, no one moved! Continuing the game.", 'file': None}
                    )
                    time.sleep(1.5)
                    
        # Outro
        gigi.run_character(
            viseme_data={'text': "Thanks for playing Red Light Green Light with me! That was so much fun! Bye bye!", 'file': None},
            movement_data='wave_hello'
        )
        if gigi.movement:
            gigi.movement.move_sequence(basic_sequences['home'])
            
    except Exception as e:
        print(f"[RLGL] Error: {e}")
    finally:
        if gigi.vision:
            gigi.vision.stop_vision()
        gigi.face.overlay_text = None
        gigi.stop_character()
        print("[RLGL] Gigi Red Light Green Light demo finished.")

if __name__ == "__main__":
    play_red_light_green_light()
