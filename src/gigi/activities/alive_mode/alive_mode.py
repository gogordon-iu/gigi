import os
import sys
import time
import random
import signal
import threading

from gigi.core.robot import GigiRobot as Character
from gigi.core.config import IS_ROBOT


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gigi Alive Mode")
    parser.add_argument("--no-greeting", action="store_true", help="Skip initial greeting speech and wave")
    args, _ = parser.parse_known_args()

    print("====================================================")
    print("            GIGI Showcase: Alive Mode               ")
    print("====================================================")
    
    from gigi.hardware.calibration import is_motor_calibrated
    calibrated = is_motor_calibrated()

    # Initialize character with wakeup=calibrated to avoid homing uncalibrated motors
    gigi = Character(character_name="fuzzy", wakeup=calibrated, activity="Showcase Alive")
    gigi.face.overlay_text = None
    time.sleep(1)  # Allow modules to initialize
    
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
        # Initial greeting and wave
        if not args.no_greeting:
            if calibrated:
                print("[Alive Mode] Robot is calibrated. Playing initial greeting with wave...")
                gigi.run_character(
                    viseme_data={'text': "Hello everyone! I am Gigi. It is wonderful to meet you today!", 'file': None},
                    movement_data='wave_hello'
                )
                print("[Alive Mode] Homing motors and releasing hold currents to save battery...")
                if gigi.movement:
                    gigi.movement.home_position()
                    gigi.movement.release()
            else:
                print("[Alive Mode] Robot is UNCALIBRATED! Greeting vocally without moving motors...")
                gigi.run_character(
                    viseme_data={'text': "Hello everyone! I am Gigi. It is wonderful to meet you today!", 'file': None}
                )
                if gigi.movement:
                    gigi.movement.release()
        else:
            print("[Alive Mode] Resuming ambient alive mode (skipping greeting).")
            if gigi.movement:
                if calibrated:
                    gigi.movement.home_position()
                gigi.movement.release()
        
        last_look_around_time = time.time()
        next_blink_time = time.time() + random.uniform(3.0, 6.0)
        
        print("[Alive Mode] Entering low-power facial ambient loop (screen-only, zero motor power). Press Ctrl+C or send stop signal to exit.")
        while running:
            # 1. Periodic blinking on the display (zero motor movement)
            if time.time() >= next_blink_time:
                gigi.face.run_sequence("blink")
                next_blink_time = time.time() + random.uniform(4.0, 8.0)
                
            # 2. Looking around occasionally on the display with eyes only (zero motor movement)
            if time.time() - last_look_around_time > random.uniform(7.0, 14.0):
                eye_seq = random.choice(["look_left", "look_right", "look_up", "look_down"])
                gigi.face.run_sequence(eye_seq)
                
                # Hold gaze for 1.2 to 2.2 seconds
                look_start = time.time()
                look_duration = random.uniform(1.2, 2.2)
                while running and (time.time() - look_start < look_duration):
                    time.sleep(0.1)
                
                # Return eyes to center
                gigi.face.run_sequence("idle")
                last_look_around_time = time.time()
                next_blink_time = time.time() + random.uniform(2.5, 5.0)
                
            # Sleep to prevent unnecessary CPU usage
            time.sleep(0.1)
            
    except Exception as e:
        print(f"[Alive Mode] Error in main loop: {e}")
        
    finally:
        print("[Alive Mode] Performing clean up...")
        if gigi.vision:
            gigi.vision.stop_vision()
        if gigi.movement:
            print("[Alive Mode] Ensuring all motor hold currents are released...")
            gigi.movement.release()
        gigi.stop_character()
        print("[Alive Mode] Gigi has finished cleanly.")

if __name__ == "__main__":
    main()
