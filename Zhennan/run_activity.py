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
from StrategyRAG import StrategyRAG
from interaction_manager import InteractionManager

# Offline modules — no LLM cost
from behavior_filter import check_behavior
from step_controller import StepController
from closing_checker import check_closing

# ── Feature flags ────────────────────────────────────────────────────────────
IS_STRATEGY  = True   # Use RAG-based strategy hints in LLM prompt
IS_CLOSING   = True   # Use offline keyword closing condition checker

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

movement_options = [
    "open_arms", "look_from_side_to_side", "look_left",
    "look_right", "arms_down"
]

def robot_speak(text: str, image: str = None):
    log("ROBOT", text)
    clean = strip_nonverbals(text)
    if not clean:
        return
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    for i, sentence in enumerate(sentences):
        viseme_data   = {'text': "placeholder " + sentence, 'file': None}
        movement_data = random.choice(movement_options)
        image_data    = {'filename': image} if (i == 0 and image) else None
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
rag        = StrategyRAG(catalog)           # embeddings built once here
manager    = InteractionManager(llm_client, rag)


# ------------------------------------------------------------------
# Load plan
# ------------------------------------------------------------------
plan_file = "math_activity.json"
if not os.path.exists(plan_file):
    print(f"'{plan_file}' not found.")
    sys.exit(1)

with open(plan_file) as f:
    plan = json.load(f)

log("SYSTEM", f"Loaded: {plan.get('activity_title', '?')}")


# ------------------------------------------------------------------
# Init time controller from plan
# ------------------------------------------------------------------
target_duration_str = plan.get("approximate_duration", "10 minutes")
try:
    target_minutes = float(target_duration_str.split()[0])
except Exception:
    target_minutes = 10.0

controller = StepController(target_minutes=target_minutes)


# ------------------------------------------------------------------
# Run activity
# ------------------------------------------------------------------
history      = []
steps        = plan.get("steps", plan.get("phases", []))
force_finish = False

log("STEP", "--- Activity Started ---")

for i, step in enumerate(steps):

    if force_finish and i < len(steps) - 1:
        continue

    step_type = step.get("step_type", step.get("phase_type", "unknown"))
    log("STEP", f"[Step {i+1}: {step_type.upper()}]")

    # ── Canned step ──────────────────────────────────────────────────────
    if step_type in ("canned", "introduction", "core_content", "conclusion"):
        script = step.get("robot_script", "")
        image  = step.get("image", None)
        if script:
            robot_speak(script, image)
            history.append({"role": "assistant", "content": script})
        if i < len(steps) - 1:
            time.sleep(2)

    # ── Open step ────────────────────────────────────────────────────────
    elif step_type in ("open", "open_conversation"):
        log("SYSTEM", "(Interaction phase. Say or type '/next' to advance.)")
        script = step.get("robot_script", "")
        image  = step.get("image", None)
        if script:
            robot_speak(script, image)
            history.append({"role": "assistant", "content": script})

        closing_condition = step.get("closing_condition", "")

        while True:

            # ── 1. Time check (offline) ──────────────────────────────────
            if controller.should_force_finish():
                log("SYSTEM", "Time limit reached — force finishing.")
                robot_speak(controller.wrap_up_response())
                force_finish = True
                break

            if controller.is_near_end():
                log("SYSTEM", "Approaching time limit.", terminal=False)

            # ── 2. Listen ────────────────────────────────────────────────
            user_input = robot_listen()
            
            # Start background processing for offline checks and LLM calls
            action = {"type": None, "response": None}

            def process_input():
                # ── 3. Manual advance ────────────────────────────────────────
                if user_input.strip().lower() == "/next":
                    action["type"] = "break"
                    return

                # ── 4. Behavior check (offline) ──────────────────────────────
                bad_behavior_response = check_behavior(user_input)
                if bad_behavior_response:
                    log("SYSTEM", "Behavior issue detected — canned response.")
                    action["type"] = "continue"
                    action["response"] = bad_behavior_response
                    return

                # ── 5. Append to history ─────────────────────────────────────
                history.append({"role": "user", "content": user_input})

                # ── 6. Closing condition check (offline) ─────────────────────
                if IS_CLOSING and closing_condition:
                    if check_closing(history, closing_condition, llm_client, use_llm=True):
                        log("SYSTEM", "Closing condition met — advancing step.")
                        action["type"] = "break"
                        return

                # ── 7. Generate robot response via RAG + tiny LLM ────────────
                system_prompt, user_prompt = manager.get_prompts(history, step, user_input)

                log("SYSTEM", f"system_prompt: {system_prompt}", terminal=False)
                log("SYSTEM", f"user_prompt: {user_prompt}",   terminal=False)

                robot_response = gigi.conversation.get_response(system_prompt, user_prompt)

                if not robot_response:
                    log("SYSTEM", "No response generated.")
                    action["type"] = "continue"
                    return

                # Log strategy (retrieved offline, not from LLM output)
                if IS_STRATEGY:
                    best = rag.retrieve(user_input, top_k=1)
                    if best:
                        log("SYSTEM", f"Strategy → {best[0].id}", terminal=False)

                action["type"] = "speak"
                action["response"] = robot_response

            t_process = threading.Thread(target=process_input)
            t_process.start()

            # Main thread speaks filler so GUI/Viseme works correctly
            robot_speak(random.choice(gigi.conversation.waiting_options))

            t_process.join()  # Wait for LLM processing if it's not done yet

            if action["type"] == "break":
                break
            elif action["type"] == "continue":
                if action["response"]:
                    robot_speak(action["response"])
                continue
            elif action["type"] == "speak":
                robot_speak(action["response"])
                history.append({"role": "assistant", "content": action["response"]})

            log("SYSTEM", f"Elapsed: {controller.elapsed_minutes():.1f} min", terminal=False)

            break  # one response per student turn, then listen again

log("STEP", "--- Activity Finished ---")