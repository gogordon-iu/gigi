import os
import re
import sys
import json
import time
import datetime

sys.path.append('/home/orangepi/Code/gigi')
sys.path.append('/home/orangepi/Code/gigi/Character')

from Character.speech import Speech
from Character.hearing import Hearing

from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from interaction_manager import InteractionManager
from coordinator import ActivityCoordinator


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(log_dir, f"activity_{timestamp}.txt")

def log(source: str, message: str, terminal: bool = True):
    now   = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{now}] [{source}] {message}"
    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    if terminal:
        prefix = {"ROBOT": "\n[ROBOT]", "STUDENT": "\n[STUDENT]",
                  "SYSTEM": "\n[System]", "STEP": "\n"}.get(source, "\n")
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
speech  = Speech(languages="en", activity="educational_activity", child=True)
hearing = Hearing(verbose=False)

def robot_speak(text: str):
    log("ROBOT", text)
    clean = strip_nonverbals(text)
    if not clean:
        return

    with open(os.devnull, 'w') as devnull:
        null_fd = devnull.fileno()
        saved_stdout = os.dup(1)
        saved_stderr = os.dup(2)
        try:
            os.dup2(null_fd, 1)  # suppress "Generating speech..."
            os.dup2(null_fd, 2)  # suppress ffmpeg wall of text
            speech.run_speech(text=clean)
        finally:
            os.dup2(saved_stdout, 1)
            os.dup2(saved_stderr, 2)
            os.close(saved_stdout)
            os.close(saved_stderr)

def robot_listen() -> str:
    print("\n[Listening...]")
    hearing.texts = []
    hearing.run_hearing()

    if hearing.texts:
        heard = hearing.texts[-1]
        log("STUDENT", heard)
        return heard

    # Fallback to keyboard if mic fails
    print("[STT failed – type or press Enter to skip]")
    typed = input("[STUDENT (typed)]: ").strip()
    if typed:
        log("STUDENT (typed)", typed)
    return typed or "[no response]"


# ------------------------------------------------------------------
# Init LLM pipeline
# ------------------------------------------------------------------
llm_client  = LLMClient()
catalog     = StrategyCatalog()
manager     = InteractionManager(llm_client, catalog)
coordinator = ActivityCoordinator(llm_client)

def is_closing_condition_met(history: list, closing_condition: str) -> bool:
    """Ask the LLM a simple yes/no: has the closing condition been met?"""
    history_str = "\n".join(f"{e['role']}: {e['content']}" for e in history[-6:])
    
    system_prompt = (
        "You are a strict evaluator. Given a conversation history and a closing condition, "
        "reply with ONLY 'YES' or 'NO'. Nothing else."
    )
    user_prompt = (
        f"Closing condition: {closing_condition}\n\n"
        f"Conversation history:\n{history_str}\n\n"
        "Has the closing condition been met? Reply YES or NO only."
    )
    
    result = llm_client.get_completion(system_prompt, user_prompt)
    return result and "YES" in result.upper()
# ------------------------------------------------------------------
# Load plan
# ------------------------------------------------------------------
plan_file = "activity_plan.json"
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
start_time   = time.time()
force_finish = False

log("STEP", "--- Activity Started ---")

for i, step in enumerate(steps):

    if force_finish and i < len(steps) - 1:
        continue

    step_type = step.get("step_type", step.get("phase_type", "unknown"))
    log("STEP", f"[Step {i+1}: {step_type.upper()}]")

    # ── Canned step ──────────────────────────────────────────────
    if step_type in ("canned", "introduction", "core_content", "conclusion"):
        script = step.get("robot_script", "")
        if script:
            robot_speak(script)
            history.append({"role": "assistant", "content": script})
        if i < len(steps) - 1:
            time.sleep(2)

    # ── Open step ────────────────────────────────────────────────
    elif step_type in ("open", "open_conversation"):
        log("SYSTEM", "(Interaction phase. Say or type '/next' to advance.)")

        if step.get("robot_script"):
            robot_speak(step["robot_script"])
            history.append({"role": "assistant", "content": step["robot_script"]})

        while True:
            user_input = robot_listen()

            if user_input.strip().lower() == "/next":
                break

            history.append({"role": "user", "content": user_input})

            closing = step.get("closing_condition", "")
            if closing and is_closing_condition_met(history, closing):
                log("SYSTEM", "Closing condition met — advancing.")
                break

            # Coordinator check
            elapsed = (time.time() - start_time) / 60.0
            intervention = coordinator.check_intervention(history, plan, step, elapsed)

            if intervention.get("action") == "intervene":
                log("SYSTEM", f"Coordinator: {intervention.get('reason')}")
                response = intervention.get("response", "")
                if response:
                    robot_speak(response)
                    history.append({"role": "assistant", "content": response})
                if intervention.get("override_next_step"):
                    force_finish = True
                    break
                continue

            # Interaction manager
            print("...")
            robot_response = manager.generate_turn(history, step)

            if not robot_response:
                log("SYSTEM", "No response generated.")
                continue

            content = robot_response

            # Log strategy tag, don't speak it
            m = re.search(r"\[STRATEGY:\s*(.*?)\]", content)
            if m:
                log("SYSTEM", f"Strategy → {m.group(1)}", terminal=False)
                content = content.replace(m.group(0), "").strip()

            # Advance step
            if "[NEXT_STEP]" in content:
                clean = content.replace("[NEXT_STEP]", "").strip()
                if clean:
                    robot_speak(clean)
                    history.append({"role": "assistant", "content": clean})
                log("SYSTEM", "Moving to next step.")
                break

            robot_speak(content)
            history.append({"role": "assistant", "content": content})

            log("SYSTEM", f"Elapsed: {elapsed:.1f} min", terminal=False)

log("STEP", "--- Activity Finished ---")