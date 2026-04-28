import os
import re
import sys
import json
import time
import datetime
import random
import threading
if os.name=="posix":
    sys.path.append('/home/orangepi/Code/gigi')
    sys.path.append('/home/orangepi/Code/gigi/Character')
else:
    sys.path.append('C:/Users/gowth/Desktop/gigi')
    sys.path.append('C:/Users/gowth/Desktop/gigi/Character')

from Character.character import Character

from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from interaction_manager import InteractionManager  # ← removed first_sentence

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
log_filename = os.path.join(log_dir, f"activity_{timestamp}.txt")

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
    gigi.hearing.texts = []
    gigi.run_character(movement_data="home")
    gigi.listen_backchannel()

    if gigi.hearing.texts:
        heard = gigi.hearing.texts[-1]
        log("STUDENT", heard)
        return heard

    print("[STT failed – type or press Enter to skip]")
    typed = input("[STUDENT (typed)]: ").strip()
    if typed:
        log("STUDENT (typed)", typed)
    return typed or "[no response]"


# ------------------------------------------------------------------
# Init LLM + offline pipeline
# ------------------------------------------------------------------
llm_client = LLMClient()
catalog    = StrategyCatalog()
manager    = InteractionManager(gigi.conversation, catalog)


# ------------------------------------------------------------------
# Load plan
# ------------------------------------------------------------------
plan_file = "activity_plan_new.json"
if not os.path.exists(plan_file):
    print(f"'{plan_file}' not found.")
    sys.exit(1)

with open(plan_file) as f:
    plan = json.load(f)

log("SYSTEM", f"Loaded: {plan.get('activity_title', '?')}")


# ------------------------------------------------------------------
# Run activity
# ------------------------------------------------------------------
history      = []
steps        = plan.get("steps", plan.get("phases", []))

log("STEP", "--- Activity Started ---")

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
        image  = step.get("image_path", step.get("image", None))
        if script:
            robot_speak(script, image)
            history.append({"role": "assistant", "content": script})
        if i < len(steps) - 1:
            time.sleep(2)

    # ── Open step ────────────────────────────────────────────────────────
    elif step_type in ("open", "open_conversation"):
        log("SYSTEM", "(Interaction phase. Say or type '/next' to advance.)")
        script = step.get("robot_script", "")
        image  = step.get("image_path", step.get("image", None))
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
            robot_speak(random.choice(gigi.conversation.waiting_options))

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
                
                # Robust check for next step tag (handles [NEXT STEP], [next_step], etc.)
                next_step_match = re.search(r"\[NEXT[ _]STEP\]", robot_response, re.IGNORECASE)
                
                if next_step_match:
                    log("SYSTEM", "Robot decided to move to next step.")
                    # Strip the tag and anything after it for the spoken response
                    clean_text = robot_response[:next_step_match.start()].strip()
                    if clean_text:
                        robot_speak(clean_text)
                        history.append({"role": "assistant", "content": clean_text})
                    break # exit the while True loop for this step
                else:
                    robot_speak(robot_response)
                    history.append({"role": "assistant", "content": robot_response})

log("STEP", "--- Activity Finished ---")