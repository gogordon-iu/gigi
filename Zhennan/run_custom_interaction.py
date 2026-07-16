import os
import re
import sys
import json
import time
import datetime
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(current_dir)
char_dir = os.path.join(gigi_dir, "Character")

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)
if char_dir not in sys.path:
    sys.path.append(char_dir)

from Character.character import Character

# Logging
log_dir      = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"custom_interaction_{timestamp}.txt")

def log(source: str, message: str, terminal: bool = True):
    now   = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{now}] [{source}] {message}"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    if terminal:
        prefix = {
            "ROBOT":   "\n[ROBOT]",
            "USER":    "\n[USER]",
            "SYSTEM":  "\n[System]",
            "STATE":   "\n"
        }.get(source, "\n")
        print(f"{prefix}: {message}")

def find_file_in_dir(directory: str, filename: str, extensions: list = None) -> str:
    base_name = os.path.splitext(os.path.basename(filename))[0]
    for root, _, files in os.walk(directory):
        for file in files:
            file_base, file_ext = os.path.splitext(file)
            if file_base == base_name:
                if not extensions or file_ext.lower() in extensions:
                    return os.path.join(root, file).replace("\\", "/")
    return None

def strip_nonverbals(text: str) -> str:
    clean = re.sub(r"\[([^\]]+)\]", "", text).strip()
    return re.sub(r" {2,}", " ", clean).strip()

# Initialize Gigi
gigi = Character()
gigi.show_camera_feed = False
gigi.set_activity(activity_name="custom_interaction")

movement_options = [
    "look_from_side_to_side", "look_left", "look_right"
]

def robot_speak(text: str, image: str = None, movement: str = None, expression: str = None):
    log("ROBOT", text)
    clean = strip_nonverbals(text)
    if not clean:
        return
        
    speaker = getattr(gigi, "current_speaker", None)
    if not speaker and gigi.egocentric_db:
        speaker = max(gigi.egocentric_db.keys(), key=lambda k: gigi.egocentric_db[k].get("timestamp", 0))
    if speaker:
        gigi.lookat_person(speaker)
        
    if expression and gigi.face:
        gigi.face.run_sequence(expression)
        
    image_data = None
    if image:
        image_data = {'filename': image, 'duration': 6.0}
        
    gigi.run_character(
        viseme_data={'text': clean, 'file': None},
        movement_data=movement or (random.choice(movement_options) if random.random() < 0.5 else None),
        image_data=image_data,
        restore_face=True
    )

def robot_listen(timeout: int = 10) -> str:
    print("\n[Listening...]")
    if gigi.hearing:
        gigi.hearing.texts = []
        
    speaker = getattr(gigi, "current_speaker", None)
    if not speaker and gigi.egocentric_db:
        speaker = max(gigi.egocentric_db.keys(), key=lambda k: gigi.egocentric_db[k].get("timestamp", 0))
    if speaker:
        gigi.lookat_person(speaker)
    else:
        gigi.run_character(movement_data="home")
        
    if gigi.face:
        gigi.face.guidance = "speak"
        
    if gigi.vision and not gigi.vision.running:
        gigi.vision.run_vision(show_window=False)
        
    import os
    if gigi.hearing and os.environ.get("DISABLE_MIC") != "1":
        gigi.listen_fluid(timeout=timeout, show_camera_feed=False)
        
    if gigi.vision and gigi.vision.running:
        gigi.update_egocentric_locations()
        
    if gigi.face:
        gigi.face.guidance = None
        
    if gigi.hearing and gigi.hearing.texts:
        heard = gigi.hearing.texts[-1]
        log("USER", heard)
        return heard

    print("[STT failed – type or press Enter to skip]")
    typed = input("[USER (typed)]: ").strip()
    if typed:
        log("USER (typed)", typed)
    return typed or "[no response]"

def interpolate_vars(text: str, state_vars: dict) -> str:
    def _rep(m):
        var_name = m.group(1)
        return str(state_vars.get(var_name, m.group(0)))
    return re.sub(r"\{(\w+)\}", _rep, text)

# Main interpreter logic
def main():
    if len(sys.argv) < 2:
        print("Usage: python run_custom_interaction.py <folder_name>")
        sys.exit(1)
        
    activity_folder = sys.argv[1]
    gigi_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    activity_dir = os.path.join(gigi_dir, "Assets", activity_folder)
    
    json_path = os.path.join(activity_dir, "custom_interaction.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist.")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    log("SYSTEM", f"Loaded custom interaction: {config.get('interaction_title', '?')}")
    
    state_vars = config.get("variables", {})
    states = config.get("states", {})
    
    # Locate initial state (default to 'welcome' or first state)
    current_state_name = "welcome" if "welcome" in states else next(iter(states.keys()))
    
    try:
        while current_state_name != "exit":
            log("STATE", f"--- Entering State: {current_state_name} ---")
            state = states.get(current_state_name)
            if not state:
                log("SYSTEM", f"Error: State '{current_state_name}' not defined. Exiting.")
                break
                
            actions = state.get("actions", [])
            for action in actions:
                action_type = action.get("type")
                
                if action_type == "speak":
                    raw_text = action.get("text", "")
                    text = interpolate_vars(raw_text, state_vars)
                    movement = action.get("movement")
                    expression = action.get("expression")
                    image_ref = action.get("image")
                    image = None
                    if image_ref:
                        image = find_file_in_dir(activity_dir, image_ref, extensions=['.png', '.jpg', '.jpeg'])
                    robot_speak(text, image, movement, expression)
                    time.sleep(1.0)
                    
                elif action_type == "listen":
                    var_name = action.get("variable")
                    timeout = action.get("timeout", 10)
                    user_input = robot_listen(timeout)
                    if var_name:
                        state_vars[var_name] = user_input
                        
                elif action_type == "vision":
                    mode = action.get("mode")
                    target = action.get("target")
                    var_name = action.get("variable")
                    timeout = action.get("timeout", 8)
                    
                    found = False
                    if gigi.vision:
                        gigi.vision.run_vision(show_window=False)
                        if mode == "look_for_gesture":
                            print(f"[Vision] Scanning for gesture: {target}...")
                            res = gigi.vision.look_for(what={"gesture": target}, timeout=float(timeout))
                            found = bool(res and res.get("found"))
                        else:
                            print(f"[Vision] Scanning for target face...")
                            gigi.lookat_something(what="face", timeout=float(timeout))
                            found = True
                        gigi.vision.stop_vision()
                    else:
                        # Fallback for offline simulation
                        print(f"[Vision Simulation] Simulating success for mode {mode}")
                        found = True
                        time.sleep(1.5)
                        
                    if var_name:
                        state_vars[var_name] = found
                        
                elif action_type == "llm":
                    sys_prompt = action.get("system_prompt", "You are an assistant.")
                    raw_user_prompt = action.get("user_prompt", "")
                    user_prompt = interpolate_vars(raw_user_prompt, state_vars)
                    var_name = action.get("variable")
                    
                    log("SYSTEM", f"Calling LLM for evaluation...")
                    response = gigi.conversation.get_response(system_prompt=sys_prompt, user_prompt=user_prompt)
                    log("SYSTEM", f"LLM reply: '{response.strip()}'")
                    if var_name:
                        state_vars[var_name] = response.strip()
                        
                elif action_type == "evaluate":
                    expression = action.get("expression", "")
                    try:
                        # Run variable updates in the state_vars context
                        exec(expression, {}, state_vars)
                        print(f"[Evaluate] Executed '{expression}' successfully. Current vars: {state_vars}")
                    except Exception as eval_err:
                        log("SYSTEM", f"Evaluation error for '{expression}': {eval_err}")
                        
                elif action_type == "display":
                    disp_type = action.get("display_type")
                    val = action.get("value")
                    if disp_type == "image":
                        image_path = find_file_in_dir(activity_dir, val, extensions=['.png', '.jpg', '.jpeg']) if val else None
                        if gigi.face:
                            gigi.face.display_image_file(image_path)
                    elif disp_type == "video":
                        video_path = find_file_in_dir(activity_dir, val, extensions=['.mp4', '.avi', '.mkv']) if val else None
                        if gigi.face:
                            gigi.face.display_video_file(video_path)
                    elif disp_type == "expression":
                        if gigi.face and val:
                            gigi.face.run_sequence(val)
                            
            # Process transitions
            transitions = state.get("transitions", [])
            next_state_name = None
            for trans in transitions:
                condition = trans.get("condition")
                target = trans.get("target")
                
                if not condition:
                    # Default transition
                    next_state_name = target
                    break
                else:
                    # Evaluate condition
                    try:
                        cond_val = eval(condition, {}, state_vars)
                        if cond_val:
                            next_state_name = target
                            break
                    except Exception as cond_err:
                        log("SYSTEM", f"Condition eval error for '{condition}': {cond_err}")
                        
            if not next_state_name:
                log("SYSTEM", "Warning: No transition matched. Exiting interaction loop.")
                break
                
            current_state_name = next_state_name
            time.sleep(1.0)
            
    finally:
        log("STATE", "--- Custom Interaction Finished ---")
        print("Cleaning up resources...")
        if hasattr(gigi, "movement") and gigi.movement:
            gigi.movement.release()
        if hasattr(gigi, "vision") and gigi.vision and gigi.vision.running:
            gigi.vision.stop_vision()
        if hasattr(gigi, "face") and gigi.face:
            gigi.face.stop_face()
        gigi.stop_character()
        print("Cleanup done!")

if __name__ == "__main__":
    main()
