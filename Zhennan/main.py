import os
import re
import json
import datetime
import time
from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from interaction_manager import InteractionManager
from coordinator import ActivityCoordinator
from robot_interface import RobotInterface



def main():
    # ------------------------------------------------------------------ #
    # Logging setup                                                        #
    # ------------------------------------------------------------------ #
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"interaction_log_{timestamp}.txt")

    def log_interaction(source: str, message: str, print_to_terminal: bool = True):
        now       = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{now}] [{source}] {message}"

        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

        if print_to_terminal:
            if source == "SYSTEM":
                print(f"\n[System]: {message}")
            elif source == "ROBOT":
                print(f"\n[ROBOT]: {message}")
            elif source == "STEP":
                print(f"\n{message}")
            elif source == "INFO":
                print(message)
            # STUDENT input is already printed by the listen helper below

    log_interaction("INFO", "Initialising Robot-Assisted Activity System…")

    # ------------------------------------------------------------------ #
    # Component setup                                                      #
    # ------------------------------------------------------------------ #
    try:
        llm_client = LLMClient()
    except Exception as exc:
        log_interaction("SYSTEM", f"Error initialising LLM Client: {exc}")
        return

    catalog     = StrategyCatalog()
    manager     = InteractionManager(llm_client, catalog)
    coordinator = ActivityCoordinator(llm_client)

    # Boot the physical robot interface (Vision / Speech / Hearing)
    robot = RobotInterface(pause_vision_during_speech=True, child_voice=True)
    robot.start()

    # ------------------------------------------------------------------ #
    # Helper: robot speaks (logs + TTS)                                   #
    # ------------------------------------------------------------------ #
    def robot_speak(text: str):
        log_interaction("ROBOT", text)
        robot.speak(text)                  # executes non-verbals + TTS

    # ------------------------------------------------------------------ #
    # Helper: robot listens (STT + logs + fallback)                       #
    # ------------------------------------------------------------------ #
    def robot_listen() -> str:
        print("\n[Listening…]")
        heard = robot.listen()

        if heard:
            print(f"\n[STUDENT]: {heard}")
            log_interaction("STUDENT", heard)
            return heard

        # Fallback: if STT fails, allow manual keyboard entry so the
        # session isn't completely blocked by a mic/hardware issue.
        print("[STT failed – type student input or press Enter to skip]")
        fallback = input("[STUDENT (typed)]: ").strip()
        if fallback:
            log_interaction("STUDENT (typed)", fallback)
        return fallback or "[no response]"

    # ------------------------------------------------------------------ #
    # Load activity plan                                                   #
    # ------------------------------------------------------------------ #
    plan_filename = "activity_plan.json"
    if not os.path.exists(plan_filename):
        log_interaction("SYSTEM", f"'{plan_filename}' not found.")
        robot.stop()
        return

    try:
        with open(plan_filename, "r") as f:
            plan = json.load(f)
        log_interaction("INFO", f"Loaded plan: {plan.get('activity_title', '?')}")
    except Exception as exc:
        log_interaction("SYSTEM", f"Error loading plan: {exc}")
        robot.stop()
        return

    # ------------------------------------------------------------------ #
    # Announce present students (optional but nice to have)               #
    # ------------------------------------------------------------------ #
    present = robot.get_present_students()
    if present:
        log_interaction("INFO", f"Recognised students: {', '.join(present)}")

    # ------------------------------------------------------------------ #
    # Execution loop                                                       #
    # ------------------------------------------------------------------ #
    history     = []
    steps       = plan.get("steps", plan.get("phases", []))
    start_time  = time.time()
    force_finish = False

    log_interaction("STEP", "--- Activity Started ---")

    for i, step in enumerate(steps):

        # Skip to final step when coordinator forces wrap-up
        if force_finish and i < len(steps) - 1:
            continue

        step_type = step.get("step_type", step.get("phase_type", "unknown"))
        log_interaction("STEP", f"[Step {i+1}: {step_type.upper()}]")

        # ---------------------------------------------------------------- #
        # CANNED step – static robot script                                #
        # ---------------------------------------------------------------- #
        if step_type in ("canned", "introduction", "core_content", "conclusion"):
            script = step.get("robot_script", "")
            if script:
                robot_speak(script)
                history.append({"role": "assistant", "content": script})

            # Pause briefly between canned steps (no keyboard needed)
            if i < len(steps) - 1:
                time.sleep(2)

        # ---------------------------------------------------------------- #
        # OPEN step – live student interaction                             #
        # ---------------------------------------------------------------- #
        elif step_type in ("open", "open_conversation"):
            log_interaction("INFO", "(Interaction phase. Say '/next' to force-advance.)")

            # Optional opening line for this open step
            if step.get("robot_script"):
                robot_speak(step["robot_script"])
                history.append({"role": "assistant", "content": step["robot_script"]})

            while True:
                # --- Listen ---
                user_input = robot_listen()

                if user_input.strip().lower() == "/next":
                    break

                history.append({"role": "user", "content": user_input})

                # -------------------------------------------------------- #
                # Enrich history entry with vision snapshot                #
                # -------------------------------------------------------- #
                vision_ctx = robot.get_vision_context()
                log_interaction("SYSTEM", vision_ctx, print_to_terminal=False)

                # -------------------------------------------------------- #
                # Coordinator check                                        #
                # -------------------------------------------------------- #
                elapsed_minutes = (time.time() - start_time) / 60.0
                intervention = coordinator.check_intervention(
                    history, plan, step, elapsed_minutes,
                    vision_context=vision_ctx          # ← new kwarg
                )

                if intervention.get("action") == "intervene":
                    log_interaction("SYSTEM", f"Coordinator intervened: {intervention.get('reason')}")
                    response = intervention.get("response")
                    if response:
                        robot_speak(response)
                        history.append({"role": "assistant", "content": response})

                    if intervention.get("override_next_step"):
                        log_interaction("SYSTEM", "Coordinator forcing activity wrap-up.")
                        force_finish = True
                        break

                    continue   # skip normal interaction manager turn

                # -------------------------------------------------------- #
                # Normal interaction manager turn                          #
                # -------------------------------------------------------- #
                print("…")
                robot_response = manager.generate_turn(history, step,
                                                       vision_context=vision_ctx)  # ← new kwarg

                if not robot_response:
                    log_interaction("SYSTEM", "Robot failed to generate a response.")
                    continue

                content_to_speak = robot_response

                # Extract strategy tag for logging (don't speak it)
                strategy_tag = None
                strategy_match = re.search(r"\[STRATEGY:\s*(.*?)\]", content_to_speak)
                if strategy_match:
                    strategy_tag     = strategy_match.group(1)
                    content_to_speak = content_to_speak.replace(strategy_match.group(0), "").strip()
                    log_interaction("SYSTEM", f"Strategy → {strategy_tag}")

                # Check if the LLM wants to advance to the next step
                if "[NEXT_STEP]" in content_to_speak:
                    log_interaction("SYSTEM", "Robot decided to advance to next step.")
                    clean = content_to_speak.replace("[NEXT_STEP]", "").strip()
                    if clean:
                        robot_speak(clean)
                        history.append({"role": "assistant", "content": clean})
                    break

                robot_speak(content_to_speak)
                history.append({"role": "assistant", "content": content_to_speak})

                # Periodic time log (file only)
                elapsed_min = (time.time() - start_time) / 60.0
                log_interaction("SYSTEM", f"Time elapsed: {elapsed_min:.1f} min",
                                print_to_terminal=False)

    log_interaction("STEP", "--- Activity Finished ---")
    robot.stop()


if __name__ == "__main__":
    main()