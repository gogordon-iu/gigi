import json
import sys
import os
import time
import socket
import threading
import subprocess
import random
import re

# Append paths to import Character module
char_dir = os.path.dirname(os.path.abspath(__file__))
gigi_dir = os.path.dirname(char_dir)
if char_dir not in sys.path:
    sys.path.append(char_dir)
if gigi_dir not in sys.path:
    sys.path.append(gigi_dir)
scripts_dir = os.path.abspath(os.path.join(gigi_dir, "Scripts"))
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

from character import Character
from characterDefinitions import IS_ROBOT, CHARACTER_FOLDER
from scriptAssets import get_scripts
from faceDefinitions import basic_sequences, global_parts

# Bluetooth RFCOMM Channel & TCP Fallback Port
RFCOMM_CHANNEL = 1
TCP_PORT = 5005

# Global character instance and state
gigi = None
alive_thread = None
alive_stop_event = threading.Event()

def alive_loop(gigi_inst, stop_event):
    """
    Background loop that keeps the robot looking at faces (if detected) and blinking (if idle).
    """
    print("[WakeUp] Alive loop started.")
    import numpy as np
    
    # Noise-minimizing tracking thresholds and state
    last_torso_move_time = 0.0
    last_neck_move_time = 0.0
    torso_cooldown = 2.5
    neck_cooldown = 1.0
    lost_face_start = None
    home_returned = False
    
    # Ensure vision is active
    if gigi_inst.vision and not gigi_inst.vision.running:
        gigi_inst.vision.run_vision()
        
    while not stop_event.is_set():
        face_detected = False
        if gigi_inst.vision and gigi_inst.vision.running:
            last_data = gigi_inst.vision.get_last_data()
            if len(last_data) > 0:
                face_detected = True
                gigi_inst.update_egocentric_locations()
                lost_face_start = None
                home_returned = False
                
                # Fetch tracking offset
                face_info = next(iter(last_data.values()))
                offset_x = face_info.get('offset', [0.0, 0.0])[0]
                norm_offset = offset_x * 2.0
                
                T_c = gigi_inst.movement.calc_normalized_angle(motor="torso") if gigi_inst.movement else 0.0
                N_c = gigi_inst.movement.calc_normalized_angle(motor="neck") if gigi_inst.movement else 0.0
                error_head = norm_offset - N_c
                
                # Eye update
                if gigi_inst.face:
                    if error_head > 0.12:
                        eye_seq = basic_sequences.get("look_left", basic_sequences["idle"])
                    elif error_head < -0.12:
                        eye_seq = basic_sequences.get("look_right", basic_sequences["idle"])
                    else:
                        eye_seq = basic_sequences["idle"]
                    
                    face_state = {}
                    for part in global_parts:
                        if part in eye_seq:
                            part_data = eye_seq[part]
                            face_state[part] = (part_data[0], part_data[1][0])
                        else:
                            face_state[part] = ("idle", "1")
                    
                    face_image = gigi_inst.face.set_face(face_state)
                    gigi_inst.face.display_face(face_image)
                
                # Torso update
                T_new = T_c
                if abs(norm_offset) > 0.25:
                    if time.time() - last_torso_move_time > torso_cooldown:
                        delta_T = norm_offset * 0.7
                        T_new = np.clip(T_c + delta_T, -0.9, 0.9)
                        last_torso_move_time = time.time()
                
                # Neck update
                N_target = norm_offset - (T_new - T_c)
                N_new = N_c
                if abs(N_target - N_c) > 0.12:
                    if time.time() - last_neck_move_time > neck_cooldown:
                        N_new = np.clip(N_c + (N_target - N_c) * 0.5, -0.9, 0.9)
                        last_neck_move_time = time.time()
                
                if (T_new != T_c or N_new != N_c) and gigi_inst.movement:
                    gigi_inst.movement.move_motors({"torso": T_new, "neck": N_new})
                    
        if not face_detected:
            if gigi_inst.face:
                # Blink
                blink_stop = threading.Event()
                gigi_inst.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=blink_stop)
                
                # Cooldown to check home position
                if lost_face_start is None:
                    lost_face_start = time.time()
                elif time.time() - lost_face_start > 5.0 and not home_returned:
                    if gigi_inst.movement:
                        gigi_inst.movement.move_motors({"torso": 0.0, "neck": 0.0})
                    home_returned = True
            else:
                time.sleep(0.1)
        else:
            time.sleep(0.05)
            
    print("[WakeUp] Alive loop stopped.")

def start_alive_loop():
    global alive_thread, alive_stop_event
    alive_stop_event.clear()
    alive_thread = threading.Thread(target=alive_loop, args=(gigi, alive_stop_event), daemon=True)
    alive_thread.start()

def stop_alive_loop():
    global alive_thread, alive_stop_event
    if alive_thread and alive_thread.is_alive():
        alive_stop_event.set()
        alive_thread.join(timeout=2.0)

def execute_script_by_name(script_name):
    """
    Executes a script dynamically. First tries in-process importing, then falls back to subprocess execution.
    """
    global gigi
    # Reset log
    gigi.activity_log = []
    
    list_of_scripts = get_scripts()
    script_info = None
    for name, info in list_of_scripts.items():
        if name.lower() == script_name.lower() or info['package_name'].lower() == script_name.lower():
            script_info = info
            break
            
    if script_info:
        try:
            print(f"[WakeUp] Importing and executing script '{script_name}' in-process...")
            pkg_name = script_info['package_name']
            if pkg_name in sys.modules:
                del sys.modules[pkg_name]
                
            scriptGraph_package = __import__(pkg_name)
            scriptGraph_instance = getattr(scriptGraph_package, script_info['class_name'])()
            scriptGraph_instance.init_graph()
            
            from script import Script
            script_instance = Script(graph=scriptGraph_instance, character=gigi)
            script_instance.generateAllSpeech()
            script_instance.check_assets()
            script_instance.run()
            return True, gigi.activity_log
        except Exception as e:
            print(f"[WakeUp] In-process execution error: {e}. Falling back to subprocess...")
            
    # Subprocess fallback
    scripts_folder = os.path.abspath(os.path.join(CHARACTER_FOLDER, "../Scripts"))
    file_path = None
    for f in os.listdir(scripts_folder):
        if f.endswith(".py") and os.path.splitext(f)[0].lower() == script_name.lower():
            file_path = os.path.join(scripts_folder, f)
            break
            
    if file_path and os.path.exists(file_path):
        try:
            print(f"[WakeUp] Executing script '{file_path}' via subprocess...")
            # Release hardware resources
            gigi.stop_character()
            time.sleep(1.0)
            
            result = subprocess.run(
                [sys.executable, file_path],
                cwd=scripts_folder,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            print("[WakeUp] Subprocess complete. Restoring character resources...")
            
            # Restore resources
            new_gigi = Character(wakeup=True)
            gigi.face = new_gigi.face
            gigi.vision = new_gigi.vision
            gigi.movement = new_gigi.movement
            gigi.speech = new_gigi.speech
            gigi.viseme = new_gigi.viseme
            gigi.conversation = new_gigi.conversation
            gigi.conversation.character = gigi
            gigi.conv = gigi.conversation
            
            # Read latest logs from logs directory if available
            log_records = []
            log_dir = os.path.abspath(os.path.join(CHARACTER_FOLDER, "../Zhennan/logs"))
            if os.path.exists(log_dir):
                log_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith("activity_") and f.endswith(".txt")]
                if log_files:
                    latest_log = max(log_files, key=os.path.getmtime)
                    if time.time() - os.path.getmtime(latest_log) < 120:
                        with open(latest_log, "r", encoding="utf-8") as lf:
                            for line in lf:
                                match = re.match(r"\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.*)", line)
                                if match:
                                    time_str, speaker, text = match.groups()
                                    log_records.append({
                                        "speaker": speaker,
                                        "text": text,
                                        "timestamp": time.time()
                                    })
            
            if not log_records:
                log_records.append({
                    "speaker": "System",
                    "text": f"Subprocess finished. Output:\n{result.stdout}",
                    "timestamp": time.time()
                })
                if result.stderr:
                    log_records.append({
                        "speaker": "Error",
                        "text": result.stderr,
                        "timestamp": time.time()
                    })
                    
            return result.returncode == 0, log_records
        except Exception as e:
            print(f"[WakeUp] Subprocess execution error: {e}")
            return False, [{"speaker": "Error", "text": str(e), "timestamp": time.time()}]
            
    return False, [{"speaker": "Error", "text": "Script not found", "timestamp": time.time()}]

def execute_activity_json(activity_json):
    """
    Executes a Zhennan activity plan JSON dynamically in-process using the global gigi instance.
    """
    global gigi
    gigi.activity_log = []
    
    try:
        print("[WakeUp] Executing activity plan in-process...")
        sys.path.append(os.path.abspath(os.path.join(CHARACTER_FOLDER, "../Zhennan")))
        
        from llm_client import LLMClient
        from strategy_catalog import StrategyCatalog
        from interaction_manager import InteractionManager
        from behavior_filter import check_behavior
        
        gigi.set_activity(activity_name="educational_activity")
        if gigi.conversation:
            gigi.conversation.use_rag = True
            
        llm_client = LLMClient()
        catalog = StrategyCatalog()
        manager = InteractionManager(gigi.conversation, catalog)
        
        movement_options = ["look_from_side_to_side", "look_left", "look_right"]
        
        def robot_speak(text, image=None):
            if not text or not text.strip():
                return
            clean = re.sub(r"\[([^\]]+)\]", "", text).strip()
            clean = re.sub(r" {2,}", " ", clean).strip()
            if not clean:
                return
            sentences = re.split(r'(?<=[.!?])\s+', clean)
            for i, sentence in enumerate(sentences):
                viseme_data = {'text': sentence, 'file': None}
                movement_data = random.choice(movement_options)
                image_data = {'filename': image, 'duration': 6.0} if (i == 0 and image) else None
                gigi.run_character(
                    viseme_data=viseme_data,
                    movement_data=movement_data,
                    image_data=image_data
                )
                
        def robot_listen():
            gigi.hearing.texts = []
            gigi.run_character(movement_data="home")
            gigi.listen_backchannel()
            if gigi.hearing.texts:
                return gigi.hearing.texts[-1]
            return "[no response]"
            
        history = []
        steps = activity_json.get("steps", activity_json.get("phases", []))
        
        for i, step in enumerate(steps):
            step_type = step.get("step_type", step.get("phase_type", "unknown"))
            print(f"[WakeUp] Activity Step {i+1}: {step_type.upper()}")
            
            if step_type in ("canned", "introduction", "core_content", "conclusion"):
                sub_steps = step.get("sub_steps", [])
                if sub_steps:
                    script = " ".join(s["text"] for s in sub_steps if s.get("text"))
                else:
                    script = step.get("robot_script", "")
                image = step.get("image_path", step.get("image", None))
                if script:
                    robot_speak(script, image)
                    history.append({"role": "assistant", "content": script})
                time.sleep(2)
                
            elif step_type in ("open", "open_conversation"):
                script = step.get("robot_script", "")
                image = step.get("image_path", step.get("image", None))
                if script:
                    robot_speak(script, image)
                    history.append({"role": "assistant", "content": script})
                    
                while True:
                    user_input = robot_listen()
                    if user_input.strip().lower() == "/next":
                        break
                        
                    bad_behavior_response = check_behavior(user_input)
                    if bad_behavior_response:
                        robot_speak(bad_behavior_response)
                        continue
                        
                    history.append({"role": "user", "content": user_input})
                    
                    action = {"response": None}
                    def process_input():
                        action["response"] = manager.generate_turn(history, step)
                        
                    t_process = threading.Thread(target=process_input)
                    t_process.start()
                    
                    if gigi.conversation:
                        robot_speak(random.choice(gigi.conversation.waiting_options))
                        
                    t_process.join()
                    
                    robot_response = action["response"]
                    if robot_response:
                        next_step_match = re.search(r"\[NEXT[ _]STEP\]", robot_response, re.IGNORECASE)
                        if next_step_match:
                            clean_text = robot_response[:next_step_match.start()].strip()
                            if clean_text:
                                robot_speak(clean_text)
                                history.append({"role": "assistant", "content": clean_text})
                            break
                        else:
                            robot_speak(robot_response)
                            history.append({"role": "assistant", "content": robot_response})
                            
        print("[WakeUp] Activity finished.")
        return True, gigi.activity_log
    except Exception as e:
        print(f"[WakeUp] In-process activity execution error: {e}")
        import traceback
        traceback.print_exc()
        return False, [{"speaker": "Error", "text": str(e), "timestamp": time.time()}]

def start_server():
    server_sock = None
    is_bluetooth = False
    
    # Try RFCOMM first
    if hasattr(socket, 'AF_BLUETOOTH'):
        try:
            print("[WakeUp] Binding classical Bluetooth RFCOMM socket...")
            server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            server_sock.bind(("", RFCOMM_CHANNEL))
            server_sock.listen(1)
            is_bluetooth = True
            print(f"[WakeUp] Bluetooth RFCOMM server listening on channel {RFCOMM_CHANNEL}")
        except Exception as e:
            print(f"[WakeUp] RFCOMM bind failed: {e}. Falling back to TCP port {TCP_PORT}...")
            if server_sock:
                server_sock.close()
            server_sock = None
            
    # Fallback to TCP
    if server_sock is None:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", TCP_PORT))
        server_sock.listen(1)
        print(f"[WakeUp] TCP Fallback server listening on 0.0.0.0:{TCP_PORT}")
        
    return server_sock, is_bluetooth

def main():
    global gigi
    print("====================================================")
    print("             GIGI Social Robot WakeUp               ")
    print("====================================================")
    
    # Wake up the robot
    gigi = Character(wakeup=True, activity="wakeup")
    
    # Start background alive tracking & blinking
    start_alive_loop()
    
    # Establish connection listener
    server_sock, is_bluetooth = start_server()
    
    while True:
        try:
            print("[WakeUp] Waiting for a connection...")
            client_sock, client_info = server_sock.accept()
            print(f"[WakeUp] Connection established from {client_info}")
            
            # Read instructions in a loop
            buffer = ""
            while True:
                data = client_sock.recv(4096)
                if not data:
                    break
                    
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                        
                    try:
                        msg = json.loads(line)
                        command = msg.get("command")
                        print(f"[WakeUp] Received command: {command}")
                        
                        if command == "run_script":
                            script_name = msg.get("script_name")
                            
                            # Pause alive loop tracking
                            stop_alive_loop()
                            
                            # Run script
                            success, log_records = execute_script_by_name(script_name)
                            
                            # Upload report
                            report = {
                                "status": "success" if success else "failed",
                                "script": script_name,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                "log": log_records
                            }
                            client_sock.sendall((json.dumps(report) + "\n").encode('utf-8'))
                            print("[WakeUp] Sent activity report.")
                            
                            # Restart alive loop
                            start_alive_loop()
                            
                        elif command == "run_activity":
                            activity_json = msg.get("activity_json")
                            
                            # Pause alive loop tracking
                            stop_alive_loop()
                            
                            # Run activity
                            success, log_records = execute_activity_json(activity_json)
                            
                            # Upload report
                            report = {
                                "status": "success" if success else "failed",
                                "activity": activity_json.get("activity_title", "Unknown"),
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                                "log": log_records
                            }
                            client_sock.sendall((json.dumps(report) + "\n").encode('utf-8'))
                            print("[WakeUp] Sent activity report.")
                            
                            # Restart alive loop
                            start_alive_loop()
                            
                        elif command == "exit":
                            print("[WakeUp] Exiting connection listener.")
                            client_sock.sendall((json.dumps({"status": "exiting"}) + "\n").encode('utf-8'))
                            break
                            
                    except json.JSONDecodeError:
                        print("[WakeUp] Invalid JSON string received.")
                        client_sock.sendall(json.dumps({"error": "Invalid JSON"}).encode('utf-8'))
                    except Exception as e:
                        print(f"[WakeUp] Error: {e}")
                        client_sock.sendall((json.dumps({"error": str(e)}) + "\n").encode('utf-8'))
                        
            client_sock.close()
            print("[WakeUp] Connection closed.")
        except KeyboardInterrupt:
            print("[WakeUp] KeyboardInterrupt received. Shutting down...")
            break
        except Exception as e:
            print(f"[WakeUp] Connection handler error: {e}")
            time.sleep(1.0)
            
    # Cleanup
    stop_alive_loop()
    server_sock.close()
    if gigi:
        gigi.stop_character()

if __name__ == "__main__":
    main()
