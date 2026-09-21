"""
Custom State-Machine Interaction Runner for Gigi robot.
Executes custom educational activities, games, and state-machine flows
synthesized by the mobile app or defined via JSON.
"""

import os
import re
import sys
import json
import time
import datetime
import random
from typing import Optional, Dict, Any

from gigi.core.robot import Character
from gigi.core.config import PROJECT_ROOT, ASSETS_DIR

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
log_dir = str(PROJECT_ROOT / "logs" / "interaction")
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"custom_interaction_{timestamp}.txt")


def log(source: str, message: str, terminal: bool = True):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{now}] [{source}] {message}"
    try:
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass
    if terminal:
        prefix = {
            "ROBOT": "\n[ROBOT]",
            "USER": "\n[USER]",
            "SYSTEM": "\n[System]",
            "STATE": "\n>>>"
        }.get(source, "\n")
        print(f"{prefix}: {message}")


def strip_nonverbals(text: str) -> str:
    """Strips non-verbal tags like [smile] from text for TTS."""
    clean = re.sub(r"\[([^\]]+)\]", "", text).strip()
    return re.sub(r" {2,}", " ", clean).strip()


def find_file_in_dir(directory: str, filename: str, extensions: list = None) -> Optional[str]:
    """Locates a media file recursively in directory."""
    if not os.path.isdir(directory):
        return None
    base_name = os.path.splitext(os.path.basename(filename))[0].lower()
    for root, _, files in os.walk(directory):
        for file in files:
            file_base, file_ext = os.path.splitext(file)
            if file_base.lower() == base_name:
                if not extensions or file_ext.lower() in extensions:
                    return os.path.join(root, file).replace("\\", "/")
    return None


def interpolate_vars(text: str, state_vars: Dict[str, Any]) -> str:
    """Interpolates {var_name} placeholders with state variables."""
    def _rep(m):
        var_name = m.group(1)
        return str(state_vars.get(var_name, m.group(0)))
    return re.sub(r"\{(\w+)\}", _rep, str(text))


def main():
    if len(sys.argv) < 2:
        print("Usage: python custom_runner.py <folder_name_or_path>")
        sys.exit(1)

    target = sys.argv[1]
    gigi_dir = str(PROJECT_ROOT)
    activity_dir = os.path.join(str(ASSETS_DIR), target) if not os.path.isabs(target) else target

    if not os.path.exists(activity_dir):
        # Fallback to direct path or Assets folder check
        activity_dir = os.path.join(gigi_dir, "Assets", target)

    json_path = os.path.join(activity_dir, "custom_interaction.json")
    if not os.path.exists(json_path):
        # Try any .json file in the folder
        if os.path.isdir(activity_dir):
            json_files = [f for f in os.listdir(activity_dir) if f.endswith('.json')]
            if json_files:
                json_path = os.path.join(activity_dir, json_files[0])
            else:
                print(f"Error: No .json configuration file found in '{activity_dir}'.")
                sys.exit(1)
        elif os.path.isfile(target):
            json_path = target
            activity_dir = os.path.dirname(target)
        else:
            print(f"Error: Interaction folder '{activity_dir}' does not exist.")
            sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    log("SYSTEM", f"Loaded custom interaction: {config.get('interaction_title', '?')}")

    # Initialize robot character
    gigi = Character(activity="custom_interaction")
    gigi.show_camera_feed = False

    def robot_speak(text: str, image: Optional[str] = None, movement: Optional[str] = None, expression: Optional[str] = None):
        log("ROBOT", text)
        clean = strip_nonverbals(text)
        if not clean:
            return

        if expression and hasattr(gigi, "face") and gigi.face:
            gigi.face.run_sequence(expression)

        sentences = re.split(r'(?<=[.!?])\s+', clean)
        for idx, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            viseme_data = {'text': sentence, 'file': None}
            if image:
                image_data = {'filename': image, 'duration': 6.0} if idx == 0 else None
                move_data = "home"
                restore = (idx == len(sentences) - 1)
            else:
                image_data = None
                move_data = movement or ("home" if idx == len(sentences) - 1 else None)
                restore = True

            gigi.run_character(
                viseme_data=viseme_data,
                movement_data=move_data,
                image_data=image_data,
                restore_face=restore
            )

    def robot_listen(timeout: float = 10.0) -> str:
        print("\n[Listening...]")
        if hasattr(gigi, "face") and gigi.face:
            gigi.face.guidance = "speak"
        if hasattr(gigi, "hearing") and gigi.hearing:
            gigi.hearing.texts = []
            gigi.run_character(movement_data="home")
            gigi.listen_backchannel(timeout=timeout, show_camera_feed=False)

        if hasattr(gigi, "face") and gigi.face:
            gigi.face.guidance = None

        if hasattr(gigi, "hearing") and gigi.hearing and gigi.hearing.texts:
            heard = gigi.hearing.texts[-1]
            log("USER", heard)
            return heard

        print("[STT complete - No voice heard or timeout]")
        return "[no response]"

    state_vars = config.get("variables", {})
    states = config.get("states", {})

    # Locate initial state (default to 'welcome' or first state)
    current_state_name = "welcome" if "welcome" in states else next(iter(states.keys()), "exit")

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
                    time.sleep(0.5)

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
                    if hasattr(gigi, "vision") and gigi.vision:
                        gigi.vision.run_vision(show_window=False)
                        if mode == "look_for_gesture":
                            print(f"[Vision] Scanning for gesture: {target}...")
                            res = gigi.vision.look_for(what={"gesture": target}, timeout=float(timeout))
                            found = bool(res and res.get("found"))
                        else:
                            print(f"[Vision] Scanning for face...")
                            gigi.lookat_something(what="face", timeout=float(timeout))
                            found = True
                        gigi.vision.stop_vision()
                    else:
                        print(f"[Vision Simulation] Simulating success for mode: {mode}")
                        found = True
                        time.sleep(1.0)

                    if var_name:
                        state_vars[var_name] = found

                elif action_type == "llm":
                    sys_prompt = action.get("system_prompt", "You are an educational robot assistant.")
                    raw_user_prompt = action.get("user_prompt", "")
                    user_prompt = interpolate_vars(raw_user_prompt, state_vars)
                    var_name = action.get("variable")

                    log("SYSTEM", f"Calling LLM...")
                    if hasattr(gigi, "conversation") and gigi.conversation:
                        response = gigi.conversation.get_response(system_prompt=sys_prompt, user_prompt=user_prompt)
                    else:
                        response = "That is very interesting!"
                    log("SYSTEM", f"LLM reply: '{response.strip()}'")
                    if var_name:
                        state_vars[var_name] = response.strip()

                elif action_type == "evaluate":
                    expression = action.get("expression", "")
                    try:
                        exec(expression, {}, state_vars)
                        print(f"[Evaluate] Executed '{expression}'. Vars: {state_vars}")
                    except Exception as eval_err:
                        log("SYSTEM", f"Evaluation error for '{expression}': {eval_err}")

                elif action_type == "display":
                    disp_type = action.get("display_type")
                    val = action.get("value")
                    if disp_type == "image":
                        image_path = find_file_in_dir(activity_dir, val, extensions=['.png', '.jpg', '.jpeg']) if val else None
                        if hasattr(gigi, "face") and gigi.face and image_path:
                            gigi.face.display_image_file(image_path)
                    elif disp_type == "expression":
                        if hasattr(gigi, "face") and gigi.face and val:
                            gigi.face.run_sequence(val)

            # Process transitions
            transitions = state.get("transitions", [])
            next_state_name = None
            for trans in transitions:
                condition = trans.get("condition")
                target = trans.get("target")

                if not condition:
                    next_state_name = target
                    break
                else:
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
            time.sleep(0.5)

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
