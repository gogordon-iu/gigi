import os
import sys
import json
import datetime
import time

# 1. Add Character directory to path
# Assuming the script is in gigi/Zhennan_new and Character is in gigi/Character
current_dir = os.path.dirname(os.path.abspath(__file__))
character_path = os.path.abspath(os.path.join(current_dir, "..", "Character"))
sys.path.append(character_path)

from character import Character
from strategy_catalog import StrategyCatalog
from interaction_manager import InteractionManager
from coordinator import ActivityCoordinator

def main():
    # --- Logging Setup ---
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"robot_interaction_log_{timestamp}.txt")
    
    def log_interaction(source, message, print_to_terminal=True):
        """Helper to write interaction to log file and optionally print to terminal."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{now}] [{source}] {message}"
        
        # Write to file
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
        
        if print_to_terminal:
            if source == "SYSTEM":
                print(f"\n[System]: {message}")
            elif source == "ROBOT":
                print(f"\n[ROBOT]: {message}")
            elif source == "INFO":
                print(message)
            elif source == "STEP":
                print(f"\n{message}")

    log_interaction("INFO", "Initializing Robot-Assisted Activity System with Character Integration...")
    
    # 2. Setup Character and Logic
    try:
        # Initialize the Character (Gigi/Fuzzy)
        # character_name="fuzzy" often has more viseme/eye options
        robot = Character(character_name="fuzzy", wakeup=True, activity="Mars_Habitat")
        
        # Use the robot's local conversation engine
        conv_engine = robot.conversation
    except Exception as e:
        log_interaction("SYSTEM", f"Error initializing Robot Character: {e}")
        import traceback
        traceback.print_exc()
        return

    catalog = StrategyCatalog()
    manager = InteractionManager(conv_engine, catalog)
    coordinator = ActivityCoordinator(conv_engine)

    # 3. Load Activity Plan
    plan_filename = "activity_plan_new.json"
    if not os.path.exists(plan_filename):
        log_interaction("SYSTEM", f"'{plan_filename}' not found.")
        return

    try:
        with open(plan_filename, "r") as f:
            plan = json.load(f)
        log_interaction("INFO", f"\nSuccessfully loaded plan from '{plan_filename}'.")
    except Exception as e:
        log_interaction("SYSTEM", f"Error loading plan from file: {e}")
        return

    # 4. Execution Loop
    history = []
    log_interaction("STEP", "--- Activity Started ---")
    
    steps = plan.get("steps", [])
    if not steps and "phases" in plan:
        steps = plan["phases"]

    start_time = time.time()
    force_finish = False

    for i, step in enumerate(steps):
        if force_finish and i < len(steps) - 1:
            continue

        step_type = step.get("step_type", step.get("phase_type", "unknown"))
        log_interaction("STEP", f"[Step {i+1}: {step_type.upper()}]")
        
        # Canned Step
        if step_type == "canned" or (step_type in ["introduction", "core_content", "conclusion"]):
            script = step.get("robot_script", "")
            if script:
                log_interaction("ROBOT", script)
                # Gigi speaks and moves
                robot.run_character(viseme_data={'text': script})
                history.append({"role": "assistant", "content": script})
            
            if i < len(steps) - 1:
                # In robot mode, we might want a short pause or a button/touch to continue
                # For now, keeping a small manual check to ensure students are ready
                input("\n(Press Enter to continue to next phase...)")
        
        # Open Step
        elif step_type == "open" or step_type == "open_conversation":
            if "robot_script" in step and step["robot_script"]:
                 log_interaction("ROBOT", step['robot_script'])
                 robot.run_character(viseme_data={'text': step['robot_script']})
                 history.append({"role": "assistant", "content": step["robot_script"]})

            while True:
                # 5. Hearing Phase
                log_interaction("INFO", "\n[Listening for student...]")
                robot.hearing.run_hearing() # This is blocking until silence
                
                if not robot.hearing.texts:
                    log_interaction("SYSTEM", "No speech detected, listening again...")
                    continue
                
                user_input = robot.hearing.texts[-1]
                log_interaction("STUDENT", f"Heard: {user_input}")
                
                if user_input.strip().lower() == "next step": # Voice command to skip
                    break
                
                history.append({"role": "user", "content": user_input})
                
                # --- Coordinator Intervention Check ---
                elapsed_minutes = (time.time() - start_time) / 60.0
                intervention = coordinator.check_intervention(history, plan, step, elapsed_minutes)
                
                if intervention.get("action") == "intervene":
                    log_interaction("SYSTEM", f"Coordinator Intervened: {intervention.get('reason')}")
                    response = intervention.get("response")
                    if response:
                        log_interaction("ROBOT", response)
                        robot.run_character(viseme_data={'text': response})
                        history.append({"role": "assistant", "content": response})
                    
                    if intervention.get("override_next_step"):
                        log_interaction("SYSTEM", "Coordinator forcing activity wrap-up.")
                        force_finish = True
                        break
                    
                    continue

                # 6. Interaction Manager Response
                log_interaction("INFO", "Thinking...")
                robot_response = manager.generate_turn(history, step)
                
                if robot_response:
                    content_to_print = robot_response

                    # Check for NEXT_STEP
                    if "[NEXT_STEP]" in content_to_print:
                        log_interaction("SYSTEM", "Robot decided to move to the next step.")
                        clean_response = content_to_print.replace("[NEXT_STEP]", "").strip()
                        # Remove strategy tag if present for the clean speech
                        import re
                        clean_response = re.sub(r"\[STRATEGY:\s*(.*?)\]", "", clean_response).strip()
                        
                        if clean_response:
                            log_interaction("ROBOT", clean_response)
                            robot.run_character(viseme_data={'text': clean_response})
                            history.append({"role": "assistant", "content": clean_response})
                        break
                    
                    # Log strategy if present
                    if "[STRATEGY:" in content_to_print:
                        match = re.search(r"\[STRATEGY:\s*(.*?)\]", content_to_print)
                        if match:
                            log_interaction("SYSTEM", f"Strategy Selected -> {match.group(1)}")
                    
                    # Clean tags for speech
                    speech_text = re.sub(r"\[STRATEGY:\s*(.*?)\]", "", content_to_print).strip()
                    
                    log_interaction("ROBOT", speech_text)
                    robot.run_character(viseme_data={'text': speech_text})
                    history.append({"role": "assistant", "content": speech_text})
                else:
                    log_interaction("SYSTEM", "Robot failed to generate response.")

                # Periodically log time
                elapsed_min = (time.time() - start_time) / 60.0
                log_interaction("SYSTEM", f"Time elapsed: {elapsed_min:.1f} min", print_to_terminal=False)

    log_interaction("STEP", "--- Activity Finished ---")
    robot.run_character(viseme_data={'text': "Great job everyone! I had so much fun learning about Mars with you today. Bye bye!"})
    robot.stop_character()

if __name__ == "__main__":
    main()
