import os
import sys
import time

# Append the necessary paths to import Character modules
# This assumes demoCapabilities.py is in gigi/Demo/ and character is in gigi/Character/
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)

character_dir = os.path.join(parent_dir, 'Character')
if character_dir not in sys.path:
    sys.path.append(character_dir)

from Character.character import Character

def demoCapabilities():
    print("Initializing Gigi for capabilities demonstration...")
    
    # Initialize character with wakeup=True to show face and move to home position
    gigi = Character(character_name="fuzzy", wakeup=True)
    
    # Allow some time for initialization
    time.sleep(2)
    
    print("Demonstrating speech and movement...")
    # Start with it showing its face and saying "hello, my name is gigi" and moving hello
    gigi.run_character(
        viseme_data={'text': 'Hello, my name is Gigi.', 'file': None},
        movement_data='wave_hello'
    )
    
    # Gigi will say "I want to show you what I can do." "I can move" then move its hands and neck.
    gigi.run_character(
        viseme_data={'text': 'I want to show you what I can do.', 'file': None}
    )
    
    gigi.run_character(
        viseme_data={'text': 'I can move.', 'file': None},
        movement_data='arms_up_and_down'
    )
    
    gigi.run_character(movement_data='look_from_side_to_side')
    
    # Go back to home position
    gigi.run_character(movement_data='home')
    
    print("Demonstrating vision capabilities...")
    # "I can also see." "Do a thumbs-up"
    gigi.run_character(
        viseme_data={'text': 'I can also see. Do a thumbs up.', 'file': None}
    )
    
    # Start vision to look for thumbs up
    if gigi.vision:
        gigi.vision.run_vision()
        print("Looking for a Thumbs Up gesture...")
        # look_for returns a dict: {'found': bool, 'data': ...}
        result = gigi.vision.look_for(what={"gesture": "Thumbs Up"}, timeout=15.0)
        
        if result and result.get('found'):
            print("Thumbs Up detected!")
            # once detected say "I like you too" and laugh
            gigi.run_character(
                viseme_data={'text': 'I like you too. Hahaha.', 'file': None},
                face_data={'sequence': 'smile'}
            )
        else:
            print("Thumbs Up not detected within timeout.")
            gigi.run_character(
                viseme_data={'text': 'I did not see a thumbs up, but that is okay.', 'file': None}
            )
        gigi.vision.stop_vision()
    else:
        print("Vision module is not enabled.")

    print("Demonstrating hearing capabilities...")
    # "I can also hear you, say 'thank you'"
    gigi.run_character(
        viseme_data={'text': 'I can also hear you. Say, thank you.', 'file': None}
    )
    
    if gigi.hearing:
        gigi.hearing.texts = []
        print("Listening for 'thank you'...")
        # Listen for backchannel for up to 10 seconds
        gigi.listen_backchannel(timeout=10)
        
        heard_text = " ".join(gigi.hearing.texts).lower()
        print(f"Heard: '{heard_text}'")
        
        # if detects "thank you" say "your welcome"
        if "thank you" in heard_text or "thanks" in heard_text:
            gigi.run_character(
                viseme_data={'text': 'You are welcome.', 'file': None}
            )
        else:
            gigi.run_character(
                viseme_data={'text': 'I did not quite catch that.', 'file': None}
            )
    else:
        print("Hearing module is not enabled.")

    # say "Now it's your turn. Hope you have fun today."
    print("Concluding demo...")
    gigi.run_character(
        viseme_data={'text': "Now it's your turn. Hope you have fun today.", 'file': None}
    )

    # Clean up and stop threads
    gigi.stop_character()
    print("Demo Capabilities finished.")

if __name__ == "__main__":
    demoCapabilities()
