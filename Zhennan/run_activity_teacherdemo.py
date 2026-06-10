import os
import re
import sys
import json
import time
import datetime
import random
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(current_dir)
char_dir = os.path.join(gigi_dir, "Character")

if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)
if char_dir not in sys.path:
    sys.path.append(char_dir)

from Character.character import Character

from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from interaction_manager_teacherdemo import InteractionManager

# Offline modules — no LLM cost
from behavior_filter import check_behavior

# ── Feature flags ────────────────────────────────────────────────────────────
IS_STRATEGY  = True   # Use RAG-based strategy hints in LLM prompt

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
log_dir      = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"activity_teacherdemo_{timestamp}.txt")

def log(source: str, message: str, terminal: bool = True):
    now   = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{now}] [{source}] {message}"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    if terminal:
        prefix = {
            "ROBOT":   "\n[ROBOT]",
            "STUDENT": "\n[STUDENT]",
            "SYSTEM":  "\n[System]",
            "STEP":    "\n"
        }.get(source, "\n")
        print(f"{prefix}: {message}")


# ------------------------------------------------------------------
# Strip non-verbal cues before TTS  e.g. [smile], [wave hands]
# ------------------------------------------------------------------
def strip_nonverbals(text: str) -> str:
    system_tags = {"STRATEGY", "NEXT_STEP"}
    def _rep(m):
        return m.group(0) if any(m.group(1).upper().startswith(t) for t in system_tags) else ""
    clean = re.sub(r"\[([^\]]+)\]", _rep, text).strip()
    return re.sub(r" {2,}", " ", clean).strip()

def find_file_in_dir(directory: str, filename: str, extensions: list = None) -> str:
    base_name = os.path.splitext(os.path.basename(filename))[0]
    for root, _, files in os.walk(directory):
        for file in files:
            file_base, file_ext = os.path.splitext(file)
            if file_base == base_name:
                if not extensions or file_ext.lower() in extensions:
                    return os.path.join(root, file).replace("\\", "/")
    return None


# ------------------------------------------------------------------
# Init hardware
# ------------------------------------------------------------------
gigi = Character()
gigi.set_activity(activity_name="educational_activity")
gigi.conversation.use_rag = IS_STRATEGY

movement_options = [
    "look_from_side_to_side", "look_left", "look_right"
]

def robot_speak(text: str, image: str = None):
    log("ROBOT", text)
    clean = strip_nonverbals(text)
    if not clean:
        return
        
    # Turn and look at the student we are talking to (if recently recognized by voice)
    if getattr(gigi, "current_speaker", None):
        gigi.lookat_person(gigi.current_speaker)
        
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    for i, sentence in enumerate(sentences):
        viseme_data   = {'text': sentence, 'file': None}
        movement_data = random.choice(movement_options)
        image_data    = {'filename': image, 'duration': 6.0} if (i == 0 and image) else None
        gigi.run_character(
            viseme_data=viseme_data,
            movement_data=movement_data,
            image_data=image_data
        )

def robot_listen() -> str:
    print("\n[Listening...]")
    if gigi.hearing:
        gigi.hearing.texts = []
    gigi.run_character(movement_data="home")
    
    if gigi.face:
        gigi.face.display_text("Speak Now")
        
    # Start vision to look for face / track speaker coordinates
    if gigi.vision and not gigi.vision.running:
        gigi.vision.run_vision()
        
    if gigi.hearing:
        gigi.listen_fluid(timeout=60)

    # Update database locations before shutting off camera
    if gigi.vision and gigi.vision.running:
        gigi.update_egocentric_locations()
        
        # If background speaker recognition matched their voice, link currently 
        # visible face coordinates to their name
        if getattr(gigi, "current_speaker", None):
            speaker_name = gigi.current_speaker
            last_data = gigi.vision.get_last_data()
            if last_data:
                face_info = next(iter(last_data.values()))
                offset_x = face_info.get('offset', [0.0, 0.0])[0]
                target_gaze_angle = gigi.lookat_coordinate(offset=offset_x)
                if target_gaze_angle is not None:
                    gigi.egocentric_db[speaker_name] = {
                        "angle": float(target_gaze_angle),
                        "timestamp": time.time()
                    }
                    try:
                        from characterDefinitions import CHARACTER_FOLDER
                        with open(os.path.join(CHARACTER_FOLDER, "egocentric_locations.json"), "w") as f:
                            json.dump(gigi.egocentric_db, f, indent=4)
                        print(f"[Activity] Dynamic registration: Linked speaker '{speaker_name}' to face coordinate {target_gaze_angle:.3f}")
                    except Exception as e:
                        print(f"[Activity] Error saving egocentric location: {e}")
                        
        gigi.vision.stop_vision()

    if gigi.face:
        gigi.face.display_text(None)

    if gigi.hearing and gigi.hearing.texts:
        heard = gigi.hearing.texts[-1]
        log("STUDENT", heard)
        return heard

    print("[STT failed – type or press Enter to skip]")
    typed = input("[STUDENT (typed)]: ").strip()
    if typed:
        log("STUDENT (typed)", typed)
    return typed or "[no response]"


def greet_and_recognize():
    log("SYSTEM", "Looking around the room for familiar faces...")
    gigi.run_character(
        viseme_data={'text': "Hello! Let me look around the room to see who is here today.", 'file': None},
        movement_data='look_from_side_to_side'
    )
    
    recognized_names = []
    if gigi.vision:
        gigi.vision.run_vision()
        start_time = time.time()
        # Look around for 5 seconds to scan faces
        while time.time() - start_time < 5.0:
            gigi.update_egocentric_locations()
            time.sleep(0.5)
            
        gigi.vision.stop_vision()
        
        # Filter names that were detected recently (in the last 10 seconds)
        now = time.time()
        for name, info in gigi.egocentric_db.items():
            if now - info.get("timestamp", 0) < 10.0:
                recognized_names.append(name)
                
    if recognized_names:
        names_str = " and ".join(recognized_names)
        gigi.run_character(
            viseme_data={'text': f"Ah, hello {names_str}! I am so happy to see you today! Let's begin our activity.", 'file': None},
            movement_data='wave_hello'
        )
    else:
        gigi.run_character(
            viseme_data={'text': "Hello everyone! I see some wonderful new faces. Welcome to our activity!", 'file': None},
            movement_data='wave_hello'
        )
    gigi.run_character(movement_data='home')

# ------------------------------------------------------------------
# Init LLM + offline pipeline
# ------------------------------------------------------------------
llm_client = LLMClient()
catalog    = StrategyCatalog()
manager    = InteractionManager(gigi.conversation, catalog)


# ------------------------------------------------------------------
# Load plan
# ------------------------------------------------------------------
if len(sys.argv) < 2:
    print("Usage: python run_activity_teacherdemo.py <activity_folder_name>")
    sys.exit(1)

activity_folder = sys.argv[1]
gigi_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
activity_dir = os.path.join(gigi_dir, "Assets", activity_folder)
json_files = [f for f in os.listdir(activity_dir) if f.endswith('.json')]
if not json_files:
    print(f"No .json file found in '{activity_dir}'.")
    sys.exit(1)
plan_file = os.path.join(activity_dir, json_files[0])

with open(plan_file, "r", encoding="utf-8") as f:
    plan = json.load(f)

log("SYSTEM", f"Loaded: {plan.get('activity_title', '?')} from {activity_dir}")


# ------------------------------------------------------------------
# Run activity
# ------------------------------------------------------------------
history      = []
steps        = plan.get("steps", plan.get("phases", []))

log("STEP", "--- Activity Started ---")

# Run greeting and face recognition to personalize the start of the session
greet_and_recognize()

for i, step in enumerate(steps):
    step_type = step.get("step_type", step.get("phase_type", "unknown"))
    log("STEP", f"[Step {i+1}: {step_type.upper()}]")

    # ── Canned step ──────────────────────────────────────────────────────
    if step_type in ("canned", "introduction", "core_content", "conclusion"):
        sub_steps = step.get("sub_steps", [])
        if sub_steps:
            script = " ".join(s["text"] for s in sub_steps if s.get("text"))
        else:
            script = step.get("robot_script", "")
        image_ref = step.get("image_filename", step.get("image_path", step.get("image", None)))
        image = None
        if image_ref:
            image = find_file_in_dir(activity_dir, image_ref, extensions=['.png', '.jpg', '.jpeg'])
        if script:
            robot_speak(script, image)
            history.append({"role": "assistant", "content": script})
        if i < len(steps) - 1:
            time.sleep(2)

    # ── Open step ────────────────────────────────────────────────────────
    elif step_type in ("open", "open_conversation"):
        log("SYSTEM", "(Interaction phase. Say or type '/next' to advance.)")
        script = step.get("robot_script", "")
        image_ref = step.get("image_filename", step.get("image_path", step.get("image", None)))
        image = None
        if image_ref:
            image = find_file_in_dir(activity_dir, image_ref, extensions=['.png', '.jpg', '.jpeg'])
        if script:
            robot_speak(script, image)
            history.append({"role": "assistant", "content": script})

        while True:

            # ── 2. Listen ────────────────────────────────────────────────
            user_input = robot_listen()

            action = {"type": None, "response": None}

            def process_input():
                # ── 3. Manual advance ────────────────────────────────────
                if user_input.strip().lower() == "/next":
                    action["type"] = "break"
                    return

                # ── 4. Behavior check (offline) ──────────────────────────
                bad_behavior_response = check_behavior(user_input)
                if bad_behavior_response:
                    log("SYSTEM", "Behavior issue detected — canned response.")
                    action["type"] = "continue"
                    action["response"] = bad_behavior_response
                    return

                # ── 5. Append to history ─────────────────────────────────
                history.append({"role": "user", "content": user_input})


                # ── 7. Generate Robot Response ───────────────────────────
                robot_response = manager.generate_turn(history, step)

                if not robot_response:
                    log("SYSTEM", "No response generated.")
                    action["type"] = "continue"
                    return

                action["type"] = "speak"
                action["response"] = robot_response

            log("SYSTEM", "Waiting for LLM response...")
            _loop_start_time = time.time()
            t_process = threading.Thread(target=process_input)
            t_process.start()

            # Main thread speaks filler so GUI/Viseme works correctly
            #robot_speak(random.choice(gigi.conversation.waiting_options))

            t_process.join()
            _loop_end_time = time.time()
            log("SYSTEM", f"Concurrent processing & filler speech duration: {_loop_end_time - _loop_start_time:.2f} seconds")

            if action["type"] == "break":
                break
            elif action["type"] == "continue":
                if action["response"]:
                    robot_speak(action["response"])
                continue
            elif action["type"] == "speak":
                robot_response = action["response"]
                
                # Clean up any potential tags the LLM might have generated
                robot_response = re.sub(r"\[?NEXT[ _]STEP\]?", "", robot_response, flags=re.IGNORECASE).strip()
                
                if robot_response:
                    robot_speak(robot_response)
                    history.append({"role": "assistant", "content": robot_response})
                
                log("SYSTEM", "Teacher demo: Moving to next step after one response.")
                break # Force exit the loop after one response

log("STEP", "--- Activity Finished ---")
