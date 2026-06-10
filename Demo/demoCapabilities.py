import os
import sys
import time
import re
import random
import json

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

def extract_name(text):
    """
    Extracts a name from common greeting phrases.
    E.g. "My name is Stephanie" -> "Stephanie"
    "I am Goren" -> "Goren"
    """
    if not text or not text.strip():
        return "Friend"
    
    # Clean text
    clean = re.sub(r'[^\w\s]', '', text).strip()
    
    # Patterns
    patterns = [
        r'\bmy name is\s+(\w+)',
        r'\bi am\s+(\w+)',
        r'\bcall me\s+(\w+)',
        r'\bthis is\s+(\w+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()
            
    # Fallback to the last word if it's a short input, or a default name
    words = clean.split()
    if len(words) <= 3:
        return words[-1].capitalize()
        
    return "Friend"

def demoCapabilities():
    print("====================================================")
    print("             GIGI Social Robot Demo                 ")
    print("====================================================")
    
    # Initialize character with wakeup=True to enable startup look/position
    gigi = Character(character_name="fuzzy", wakeup=True, activity="Demo")
    
    try:
        # 1. Warm Greeting & Move (Talk + Move)
        gigi.run_character(
            viseme_data={'text': "Hi there! I am Gigi, your friendly social robot companion!", 'file': None},
            movement_data='wave_hello'
        )
        
        gigi.run_character(
            viseme_data={'text': "I want to show you my interactive capabilities! Let's start with movement.", 'file': None},
            movement_data='open_arms'
        )
        
        gigi.run_character(
            viseme_data={'text': "I can look left, look right, and center myself again. Ta da!", 'file': None},
            movement_data='look_from_side_to_side'
        )
        gigi.run_character(movement_data='home')
        
        # 2. Testing Hearing (Listen)
        gigi.run_character(
            viseme_data={'text': "First, let's test my hearing. What is your name? Tell me clearly!", 'file': None}
        )
        
        name = "Friend"
        if gigi.hearing:
            gigi.hearing.texts = []
            print("[Demo] Listening for user's name...")
            gigi.listen_backchannel(timeout=8)
            
            heard_text = " ".join(gigi.hearing.texts).strip()
            print(f"[Demo] Raw hearing transcript: '{heard_text}'")
            if heard_text:
                name = extract_name(heard_text)
            else:
                # If nothing heard, choose a fun fallback
                name = random.choice(["Superstar", "Champion", "Buddy"])
        else:
            # Headless test fallback
            name = "Explorer"
            print("[Demo] Hearing module disabled. Defaulting name to:", name)
            time.sleep(1.0)
            
        # 3. Recognize and Remember (Vision + Egocentric Database association)
        gigi.run_character(
            viseme_data={'text': f"It is wonderful to meet you, {name}! Let me look at you to lock in your coordinates.", 'file': None}
        )
        
        # Start vision and update egocentric database
        if gigi.vision:
            gigi.vision.run_vision()
            time.sleep(2.0) # Let vision spin up and detect
            
            # Fetch last detected face(s)
            last_data = gigi.vision.get_last_data()
            if last_data:
                # Associate the first detected face with the user's name
                face_info = next(iter(last_data.values()))
                offset_x = face_info.get('offset', [0.0, 0.0])[0]
                target_gaze_angle = gigi.lookat_coordinate(offset=offset_x)
                if target_gaze_angle is not None:
                    gigi.egocentric_db[name] = {
                        "angle": float(target_gaze_angle),
                        "timestamp": time.time()
                    }
                    try:
                        # Use CHARACTER_FOLDER to write
                        from characterDefinitions import CHARACTER_FOLDER
                        with open(os.path.join(CHARACTER_FOLDER, "egocentric_locations.json"), "w") as f:
                            json.dump(gigi.egocentric_db, f, indent=4)
                        print(f"[Demo] Saved {name}'s egocentric location: {target_gaze_angle:.3f}")
                    except Exception as e:
                        print(f"[Demo] Error saving egocentric location: {e}")
            else:
                print("[Demo] No face detected, using default center coordinate.")
                gigi.egocentric_db[name] = {
                    "angle": 0.0,
                    "timestamp": time.time()
                }
            gigi.vision.stop_vision()
        else:
            # Simulated egocentric entry for headless testing
            print("[Demo] Vision disabled. Adding simulated egocentric coordinate for:", name)
            gigi.egocentric_db[name] = {
                "angle": 0.35,  # Slightly to the side
                "timestamp": time.time()
            }
            from characterDefinitions import CHARACTER_FOLDER
            with open(os.path.join(CHARACTER_FOLDER, "egocentric_locations.json"), "w") as f:
                json.dump(gigi.egocentric_db, f, indent=4)
            time.sleep(1.0)
            
        gigi.run_character(
            viseme_data={'text': f"Aha! I have saved your location, {name}, in my memory database.", 'file': None}
        )
        
        # 4. Gaze Redirection Demonstration (Gaze Shift / Remember)
        gigi.run_character(
            viseme_data={'text': "Now, watch this. I will look away to check out the view...", 'file': None}
        )
        
        # Move away
        if gigi.movement:
            gigi.movement.move_motors({"torso": -0.7, "neck": -0.2})
            time.sleep(1.5)
            
        gigi.run_character(
            viseme_data={'text': "I am completely distracted! But if I speak to you...", 'file': None}
        )
        
        # Say name. The regex parser inside run_character will automatically
        # match the name and call lookat_person(name)!
        gigi.run_character(
            viseme_data={'text': f"Hey, {name}! Look at me!", 'file': None}
        )
        
        gigi.run_character(
            viseme_data={'text': "See? My social brain automatically remembered where you were sitting and redirected my gaze!", 'file': None}
        )
        
        # 5. Gesture Recognition (See)
        gigi.run_character(
            viseme_data={'text': "Let's try one more thing. Can you give me a big thumbs up?", 'file': None}
        )
        
        detected_thumbs_up = False
        if gigi.vision:
            gigi.vision.run_vision()
            print("[Demo] Scanning for a Thumbs Up gesture...")
            result = gigi.vision.look_for(what={"gesture": "Thumbs Up"}, timeout=10.0)
            if result and result.get('found'):
                detected_thumbs_up = True
            gigi.vision.stop_vision()
        else:
            # Simulate detected thumbs up
            detected_thumbs_up = True
            print("[Demo] Vision disabled. Simulating Thumbs Up detection.")
            time.sleep(1.5)
            
        if detected_thumbs_up:
            gigi.run_character(
                viseme_data={'text': "Awesome! I saw your thumbs up! I think you are super cool too!", 'file': None},
                movement_data='clap'
            )
        else:
            gigi.run_character(
                viseme_data={'text': "I didn't quite see it, but I know you are smiling. You are awesome anyway!", 'file': None}
            )
            
        # Outro
        gigi.run_character(
            viseme_data={'text': "That concludes my capabilities demo! Thank you for playing with me today. Bye bye!", 'file': None},
            movement_data='wave_hello'
        )
        gigi.run_character(movement_data='home')
        
    except Exception as e:
        print(f"[Demo] Error during demonstration: {e}")
    finally:
        # Clean up and stop threads
        gigi.stop_character()
        print("[Demo] Gigi capabilities demonstration finished cleanly.")

if __name__ == "__main__":
    demoCapabilities()
