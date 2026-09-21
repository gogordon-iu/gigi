import os
import sys
import time

from gigi.core.robot import GigiRobot as Character

def test_follow_face():
    print("==================================================")
    print("        Gigi Face-Tracking (Follow Face) Test     ")
    print("==================================================")
    print("Initializing Gigi Character...")
    
    # Initialize character (select fuzzy, wake up motors, set activity)
    gigi = Character(character_name="fuzzy", wakeup=True, activity="FollowFaceTest")
    
    # Check if we have vision and movement modules enabled
    if not gigi.vision:
        print("[Error] Vision module is not enabled or failed to initialize.")
        return
    if not gigi.movement:
        print("[Error] Movement module is not enabled or failed to initialize.")
        return

    print("\nStarting Face-Tracking loop for 30 seconds.")
    print("Look at the camera and move left/right to test torso centering.")
    print("Watch the terminal for detailed debug metrics.\n")
    
    try:
        # Run follow_face with a 30 second timeout
        gigi.follow_face(timeout=30)
    except KeyboardInterrupt:
        print("\nFace-tracking test interrupted by user.")
    except Exception as e:
        print(f"\nError occurred during face tracking: {e}")
    finally:
        # Stop character threads and close windows
        print("Cleaning up character and stopping threads...")
        gigi.stop_character()
        print("Test finished cleanly.")

if __name__ == "__main__":
    test_follow_face()
