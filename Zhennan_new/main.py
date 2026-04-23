import os
import json
import datetime
import time
from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from interaction_manager import InteractionManager
from coordinator import ActivityCoordinator

def main():
    # --- Logging Setup ---
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"interaction_log_{timestamp}.txt")
    
    def log_interaction(source, message, print_to_terminal=True):
        """Helper to write interaction to log file and optionally print to terminal."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{now}] [{source}] {message}"
        
        # Write to file
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
        
        # Print to terminal in original style
        if print_to_terminal:
            if source == "SYSTEM":
                print(f"\n[System]: {message}")
            elif source == "ROBOT":
                print(f"\n[ROBOT]: {message}")
            elif source == "STUDENT":
                # Only log student input here, it's already printed by input() in the loop
                pass
            elif source == "INFO":
                print(message)
            elif source == "STEP":
                print(f"\n{message}")

    log_interaction("INFO", "Initializing Robot-Assisted Activity System...")
    
    # 1. Setup
    try:
        llm_client = LLMClient()
    except Exception as e:
        log_interaction("SYSTEM", f"Error initializing LLM Client: {e}")
        return

    catalog = StrategyCatalog()
    manager = InteractionManager(llm_client, catalog)
    coordinator = ActivityCoordinator(llm_client)

    # 2. Load Activity Plan
    plan_filename = "activity_plan.json"
    if not os.path.exists(plan_filename):
        log_interaction("SYSTEM", f"'{plan_filename}' not found.")
        log_interaction("INFO", "Please run 'python3 app.py' first.")
        return

    try:
        with open(plan_filename, "r") as f:
            plan = json.load(f)
        log_interaction("INFO", f"\nSuccessfully loaded plan from '{plan_filename}'.")
    except Exception as e:
        log_interaction("SYSTEM", f"Error loading plan from file: {e}")
        return

    # 3. Execution Loop
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
                history.append({"role": "assistant", "content": script})
            
            if i < len(steps) - 1:
                input("\n(Press Enter to continue...)")
        
        # Open Step
        elif step_type == "open" or step_type == "open_conversation":
            log_interaction("INFO", "\n(Interaction Phase. Type '/next' to force next step, or wait for robot to decide.)")
            
            if "robot_script" in step and step["robot_script"]:
                 log_interaction("ROBOT", step['robot_script'])
                 history.append({"role": "assistant", "content": step["robot_script"]})

            while True:
                user_input = input("\n[STUDENT]: ")
                log_interaction("STUDENT", user_input)
                
                if user_input.strip() == "/next":
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
                        history.append({"role": "assistant", "content": response})
                    
                    if intervention.get("override_next_step"):
                        log_interaction("SYSTEM", "Coordinator forcing activity wrap-up.")
                        force_finish = True
                        break
                    
                    # If it was a behavior correction or question, we skip the normal interaction manager
                    continue

                print("...")
                robot_response = manager.generate_turn(history, step)
                
                if robot_response:
                    content_to_print = robot_response

                    # Check for strategy tag
                    strategy_tag = None
                    if "[STRATEGY:" in content_to_print:
                        import re
                        match = re.search(r"\[STRATEGY:\s*(.*?)\]", content_to_print)
                        if match:
                            strategy_tag = match.group(1)
                            content_to_print = content_to_print.replace(match.group(0), "").strip()
                            log_interaction("SYSTEM", f"Strategy Selected -> {strategy_tag}")

                    # Check for NEXT_STEP
                    if "[NEXT_STEP]" in content_to_print:
                        log_interaction("SYSTEM", "Robot decided to move to the next step.")
                        clean_response = content_to_print.replace("[NEXT_STEP]", "").strip()
                        if clean_response:
                            log_interaction("ROBOT", clean_response)
                            history.append({"role": "assistant", "content": clean_response})
                        break
                    
                    log_interaction("ROBOT", content_to_print)
                    history.append({"role": "assistant", "content": content_to_print})
                else:
                    log_interaction("SYSTEM", "Robot failed to generate response.")

                # Periodically log time
                elapsed_min = (time.time() - start_time) / 60.0
                log_interaction("SYSTEM", f"Time elapsed: {elapsed_min:.1f} min", print_to_terminal=False)

    log_interaction("STEP", "--- Activity Finished ---")

if __name__ == "__main__":
    main()
