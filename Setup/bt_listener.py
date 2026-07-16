#!/usr/bin/env python3
import os
import sys
import json
import time
import socket
import threading
import subprocess
import argparse
import hashlib
import base64
import struct

# Configuration
DEFAULT_TCP_PORT = 5006
DEFAULT_RFCOMM_CHANNEL = 1

# Global state
execution_manager = None
active_client = None
active_client_lock = threading.Lock()


# WebSocket helper functions
def parse_websocket_handshake(headers_str):
    key = None
    for line in headers_str.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
            break
    if not key:
        return None
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    accept_key = base64.b64encode(hashlib.sha1((key + GUID).encode('utf-8')).digest()).decode('utf-8')
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
    )
    return response.encode('utf-8')

def get_websocket_frame_length(data):
    if len(data) < 2:
        return 0
    byte2 = data[1]
    payload_len = byte2 & 0x7f
    offset = 2
    if payload_len == 126:
        offset = 4
    elif payload_len == 127:
        offset = 10
    
    masked = (byte2 & 0x80) != 0
    if masked:
        offset += 4
        
    if payload_len == 126:
        if len(data) < 4: return 0
        actual_len = struct.unpack("!H", data[2:4])[0]
    elif payload_len == 127:
        if len(data) < 10: return 0
        actual_len = struct.unpack("!Q", data[2:10])[0]
    else:
        actual_len = payload_len
        
    return offset + actual_len

def decode_websocket_frame(data):
    if len(data) < 2:
        return None, b""
    
    byte1 = data[0]
    opcode = byte1 & 0x0f
    
    if opcode == 0x8:
        return "close", b""
    
    byte2 = data[1]
    masked = (byte2 & 0x80) != 0
    payload_len = byte2 & 0x7f
    
    offset = 2
    if payload_len == 126:
        if len(data) < 4:
            return None, b""
        payload_len = struct.unpack("!H", data[2:4])[0]
        offset = 4
    elif payload_len == 127:
        if len(data) < 10:
            return None, b""
        payload_len = struct.unpack("!Q", data[2:10])[0]
        offset = 10
        
    if masked:
        if len(data) < offset + 4:
            return None, b""
        mask_key = data[offset:offset+4]
        offset += 4
    else:
        mask_key = None
        
    if len(data) < offset + payload_len:
        return None, b""
        
    payload = data[offset:offset+payload_len]
    
    if masked:
        decoded = bytearray(payload_len)
        for i in range(payload_len):
            decoded[i] = payload[i] ^ mask_key[i % 4]
        payload = bytes(decoded)
        
    msg_type = "text" if opcode == 0x1 else "binary"
    return msg_type, payload

def encode_websocket_frame(text):
    payload = text.encode('utf-8')
    payload_len = len(payload)
    
    header = bytearray([0x81])
    if payload_len < 126:
        header.append(payload_len)
    elif payload_len < 65536:
        header.append(126)
        header.extend(struct.pack("!H", payload_len))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", payload_len))
        
    return bytes(header + payload)

def get_base_dir():
    # Since this file resides in gigi/Setup/bt_listener.py, base_dir is gigi/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def scan_custom_interactions():
    """
    Scans the Assets/ directory for subdirectories starting with 'custom_interaction_'.
    Returns a list of dicts: [{"folder": folder_name, "title": interaction_title}]
    """
    base_dir = get_base_dir()
    assets_dir = os.path.join(base_dir, "Assets")
    interactions = []
    if os.path.isdir(assets_dir):
        for entry in os.listdir(assets_dir):
            entry_path = os.path.join(assets_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("custom_interaction_"):
                title = entry
                for f in os.listdir(entry_path):
                    if f.endswith(".json"):
                        json_path = os.path.join(entry_path, f)
                        try:
                            with open(json_path, "r", encoding="utf-8") as jf:
                                data = json.load(jf)
                                title = data.get("interaction_title") or data.get("title") or entry
                        except Exception as e:
                            print(f"[scan_custom_interactions] Error reading {json_path}: {e}")
                        break
                interactions.append({
                    "folder": entry,
                    "title": title
                })
    return interactions

def scan_activity_plans():
    """
    Scans the Assets/ directory for subdirectories starting with 'activity_plan_'.
    Returns a list of dicts: [{"folder": folder_name, "title": activity_title}]
    """
    base_dir = get_base_dir()
    assets_dir = os.path.join(base_dir, "Assets")
    plans = []
    if os.path.isdir(assets_dir):
        for entry in os.listdir(assets_dir):
            entry_path = os.path.join(assets_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("activity_plan_"):
                # Find any json file in this folder
                title = entry
                for f in os.listdir(entry_path):
                    if f.endswith(".json"):
                        json_path = os.path.join(entry_path, f)
                        try:
                            with open(json_path, "r", encoding="utf-8") as jf:
                                data = json.load(jf)
                                title = data.get("activity_title") or data.get("title") or entry
                        except Exception as e:
                            print(f"[scan_activity_plans] Error reading {json_path}: {e}")
                        break
                plans.append({
                    "folder": entry,
                    "title": title
                })
    return plans

def scan_files():
    """
    Scans the Demo/, Scripts/, and Zhennan/ directories for executable Python files.
    Returns:
        demos (dict): lowercase stem -> file info dict
        scripts (dict): lowercase stem -> file info dict
        zhennan (dict): lowercase stem -> file info dict
    """
    base_dir = get_base_dir()
    demo_dir = os.path.join(base_dir, "Demo")
    scripts_dir = os.path.join(base_dir, "Scripts")
    zhennan_dir = os.path.join(base_dir, "Zhennan")
    
    demos = {}
    scripts = {}
    zhennan = {}
    
    if os.path.isdir(demo_dir):
        for f in os.listdir(demo_dir):
            if f.endswith(".py") and f != "__init__.py":
                stem = os.path.splitext(f)[0]
                demos[stem.lower()] = {
                    "filename": f,
                    "stem": stem,
                    "path": os.path.abspath(os.path.join(demo_dir, f)),
                    "dir": os.path.abspath(demo_dir),
                    "type": "demo"
                }
                
    if os.path.isdir(scripts_dir):
        for f in os.listdir(scripts_dir):
            if f.endswith(".py") and f != "__init__.py":
                stem = os.path.splitext(f)[0]
                scripts[stem.lower()] = {
                    "filename": f,
                    "stem": stem,
                    "path": os.path.abspath(os.path.join(scripts_dir, f)),
                    "dir": os.path.abspath(scripts_dir),
                    "type": "script"
                }

    if os.path.isdir(zhennan_dir):
        for f in os.listdir(zhennan_dir):
            if f.endswith(".py") and f != "__init__.py":
                stem = os.path.splitext(f)[0]
                zhennan[stem.lower()] = {
                    "filename": f,
                    "stem": stem,
                    "path": os.path.abspath(os.path.join(zhennan_dir, f)),
                    "dir": os.path.abspath(zhennan_dir),
                    "type": "zhennan"
                }
                
    return demos, scripts, zhennan

def find_script(target_name):
    """
    Looks up a script, demo, or zhennan script by its name or filename.
    Returns:
        (script_info, error_details)
    """
    demos, scripts, zhennan = scan_files()
    
    # Route activity plan executions to run_activity_teacherdemo
    if target_name.startswith("activity_plan_"):
        teacher_script_key = "run_activity_teacherdemo"
        if teacher_script_key in zhennan:
            info = dict(zhennan[teacher_script_key])
            info["args"] = [target_name]
            info["filename"] = f"{info['filename']} ({target_name})"
            return info, None
            
    # Route custom interaction executions to run_custom_interaction
    if target_name.startswith("custom_interaction_"):
        custom_script_key = "run_custom_interaction"
        if custom_script_key in zhennan:
            info = dict(zhennan[custom_script_key])
            info["args"] = [target_name]
            info["filename"] = f"{info['filename']} ({target_name})"
            return info, None
            
    # Strip extension if present
    clean_name = target_name.strip()
    if clean_name.lower().endswith(".py"):
        clean_name = clean_name[:-3]
        
    key = clean_name.lower()
    
    if key in demos:
        return demos[key], None
    if key in scripts:
        return scripts[key], None
    if key in zhennan:
        return zhennan[key], None
        
    # No match found. Construct a detailed error report.
    available_demos = [info["filename"] for info in demos.values()]
    available_scripts = [info["filename"] for info in scripts.values()]
    available_zhennan = [info["filename"] for info in zhennan.values()]
    
    err_msg = f"Script, demo, or zhennan script '{target_name}' not found."
    error_details = {
        "status": "error",
        "error": "not_found",
        "message": err_msg,
        "requested": target_name,
        "available_demos": sorted(available_demos),
        "available_scripts": sorted(available_scripts),
        "available_zhennan": sorted(available_zhennan)
    }
    return None, error_details

class ConnectionWrapper:
    """
    A wrapper class to unify socket, serial, and websocket interfaces for reading/writing.
    """
    def __init__(self, conn_obj, is_serial=False, port_name=None, is_websocket=False):
        self.conn = conn_obj
        self.is_serial = is_serial
        self.port_name = port_name
        self.is_websocket = is_websocket
        self.closed = False
        self.handshake_done = False
        self.websocket_buffer = b""

    def recv(self, limit=4096):
        if self.closed:
            return b""
        try:
            if self.is_serial:
                # Read from serial port
                # Direct read using the serial port's timeout
                while not self.closed:
                    data = self.conn.read(limit)
                    if data:
                        print(f"[ConnectionWrapper] Recv serial data: {data}")
                        return data
                    # Check if connection was lost at the Bluetooth layer
                    if self.port_name and "rfcomm" in self.port_name:
                        if not is_rfcomm_connected(self.port_name):
                            print("[ConnectionWrapper] RFCOMM connection lost.")
                            self.closed = True
                            break
                    time.sleep(0.05)
                return b""
            elif self.is_websocket:
                if not self.handshake_done:
                    # Perform websocket handshake
                    data = self.conn.recv(limit)
                    if not data:
                        self.closed = True
                        return b""
                    request_str = data.decode('utf-8', errors='ignore')
                    if "Upgrade: websocket" in request_str or "upgrade: websocket" in request_str:
                        handshake_resp = parse_websocket_handshake(request_str)
                        if handshake_resp:
                            self.conn.sendall(handshake_resp)
                            self.handshake_done = True
                            print("[ConnectionWrapper] WebSocket handshake completed.")
                            return b""
                        else:
                            print("[ConnectionWrapper] Sec-WebSocket-Key missing.")
                            self.closed = True
                            return b""
                    else:
                        print("[ConnectionWrapper] Non-websocket request on WS port.")
                        self.closed = True
                        return b""
                
                # Handshake is done, read frames
                data = self.conn.recv(limit)
                if not data:
                    self.closed = True
                    return b""
                self.websocket_buffer += data
                
                # Decode frame
                msg_type, payload = decode_websocket_frame(self.websocket_buffer)
                if msg_type == "close":
                    self.closed = True
                    return b""
                elif msg_type is None:
                    # Not enough data for a full frame yet
                    return b""
                
                # Calculate frame length and slice the buffer
                frame_len = get_websocket_frame_length(self.websocket_buffer)
                if frame_len > 0:
                    self.websocket_buffer = self.websocket_buffer[frame_len:]
                return payload
            else:
                # Read from socket
                data = self.conn.recv(limit)
                if data:
                    print(f"[ConnectionWrapper] Recv socket data: {data}")
                return data
        except Exception as e:
            print(f"[ConnectionWrapper] Recv error: {e}")
            self.closed = True
            return b""

    def sendall(self, data):
        if self.closed:
            return
        try:
            print(f"[ConnectionWrapper] Sending data: {data}")
            if self.is_serial:
                self.conn.write(data)
                self.conn.flush()
            elif self.is_websocket:
                text_msg = data.decode('utf-8', errors='ignore')
                frame = encode_websocket_frame(text_msg)
                self.conn.sendall(frame)
            else:
                self.conn.sendall(data)
        except Exception as e:
            print(f"[ConnectionWrapper] Send error: {e}")
            self.closed = True

    def close(self):
        self.closed = True
        try:
            self.conn.close()
        except Exception:
            pass

class ExecutionManager:
    """
    Manages the lifecycle of the running demo or script subprocess.
    Ensures single process execution, background monitoring, and clean termination.
    """
    def __init__(self):
        self.process = None
        self.process_name = None
        self.process_type = None
        self.lock = threading.Lock()
        self.monitor_thread = None
        self.on_completion_callback = None

    def start_script(self, script_info, callback=None):
        with self.lock:
            # Terminate active process if running
            if self.process and self.process.poll() is None:
                print(f"[ExecutionManager] Terminating running script: {self.process_name}")
                try:
                    self.process.terminate()
                    for _ in range(20):
                        if self.process.poll() is not None:
                            break
                        time.sleep(0.1)
                    if self.process.poll() is None:
                        self.process.kill()
                except Exception as e:
                    print(f"[ExecutionManager] Error terminating: {e}")

            self.process_name = script_info["filename"]
            self.process_type = script_info["type"]
            self.on_completion_callback = callback

            print(f"[ExecutionManager] Executing script '{self.process_name}' in-process via subprocess fallback...")
            try:
                cmd = [sys.executable, "-u", script_info["path"]]
                if "args" in script_info:
                    cmd.extend(script_info["args"])
                # Run subprocess using system Python executable
                self.process = subprocess.Popen(
                    cmd,
                    cwd=script_info["dir"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    bufsize=1
                )
            except Exception as e:
                return False, f"Failed to launch script: {e}"

            # Start lifecycle monitoring thread
            self.monitor_thread = threading.Thread(
                target=self._monitor_lifecycle,
                args=(self.process, self.process_name, self.process_type),
                daemon=True
            )
            self.monitor_thread.start()
            return True, {
                "pid": self.process.pid,
                "name": self.process_name,
                "type": self.process_type
            }

    def stop_current(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                name = self.process_name
                print(f"[ExecutionManager] Terminating script '{name}' (PID {self.process.pid}) via command request...")
                try:
                    self.process.terminate()
                    for _ in range(20):
                        if self.process.poll() is not None:
                            break
                        time.sleep(0.1)
                    if self.process.poll() is None:
                        self.process.kill()
                    return True, f"Script '{name}' was stopped."
                except Exception as e:
                    return False, f"Failed to stop script '{name}': {e}"
            return False, "No script is currently running."

    def get_status(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return {
                    "running": True,
                    "name": self.process_name,
                    "type": self.process_type,
                    "pid": self.process.pid
                }
            return {
                "running": False,
                "name": None,
                "type": None,
                "pid": None
            }

    def _monitor_lifecycle(self, proc, name, ptype):
        def stream_logger(stream, label):
            try:
                for line in stream:
                    print(f"[{label}] {line.rstrip()}")
            except Exception:
                pass

        stdout_t = threading.Thread(target=stream_logger, args=(proc.stdout, f"Subproc OUT: {name}"), daemon=True)
        stderr_t = threading.Thread(target=stream_logger, args=(proc.stderr, f"Subproc ERR: {name}"), daemon=True)
        stdout_t.start()
        stderr_t.start()

        return_code = proc.wait()
        stdout_t.join(timeout=0.5)
        stderr_t.join(timeout=0.5)

        print(f"[ExecutionManager] Script '{name}' exited with return code {return_code}")
        if self.on_completion_callback:
            try:
                self.on_completion_callback(name, ptype, return_code)
            except Exception as e:
                print(f"[ExecutionManager] Callback error: {e}")

def send_to_active_client(msg_dict):
    global active_client
    with active_client_lock:
        if active_client:
            try:
                payload = (json.dumps(msg_dict) + "\n").encode('utf-8')
                active_client.sendall(payload)
            except Exception as e:
                print(f"[BluetoothListener] Error sending to active client: {e}")
                try:
                    active_client.close()
                except Exception:
                    pass
                active_client = None

def handle_completion_callback(name, ptype, return_code):
    status = "success" if return_code == 0 else "failed"
    send_to_active_client({
        "status": status,
        "event": "completed",
        "name": name,
        "type": ptype,
        "returncode": return_code,
        "message": f"Script '{name}' finished with return code {return_code}"
    })

def handle_client_connection(client_wrapper):
    global active_client
    
    # Check if a client is already active
    with active_client_lock:
        if active_client is not None:
            # Reject connection
            try:
                client_wrapper.sendall(json.dumps({
                    "status": "busy",
                    "message": "Another client is already connected to Gigi Bluetooth interface."
                }).encode('utf-8') + b"\n")
                client_wrapper.close()
            except Exception:
                pass
            return
        active_client = client_wrapper

    print("[BluetoothListener] Active client connection established.")
    
    # Send welcome handshake
    send_to_active_client({
        "status": "ready",
        "message": "Connected to Gigi Bluetooth script listener. Send script name or JSON command."
    })

    buffer = ""
    try:
        while not client_wrapper.closed:
            data = client_wrapper.recv(4096)
            if not data:
                break
                
            buffer += data.decode('utf-8', errors='ignore')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                
                # Process command
                process_command_line(line)
    except Exception as e:
        print(f"[BluetoothListener] Client connection handler error: {e}")
    finally:
        with active_client_lock:
            if active_client == client_wrapper:
                active_client = None
        client_wrapper.close()
        print("[BluetoothListener] Client connection closed.")

def save_plan_images(plan, plan_dir, images_dict):
    """
    Saves base64-encoded images from the images_dict to the plan's images/ directory
    and updates the local paths in the JSON.
    """
    import base64
    import re
    
    images_dir = os.path.join(plan_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    if not images_dict:
        images_dict = {}
        
    # 1. Traverse steps
    for step in plan.get("steps", []):
        # Open step check
        img_filename = step.get("image_filename")
        if img_filename and img_filename in images_dict:
            filename = os.path.basename(img_filename)
            local_path = os.path.join(images_dir, filename)
            try:
                print(f"[BluetoothListener] Saving open step base64 image: {filename} -> {local_path}")
                img_data = base64.b64decode(images_dict[img_filename])
                with open(local_path, "wb") as f:
                    f.write(img_data)
                # Update references in JSON
                step["image_path"] = f"images/{filename}"
                step["image_filename"] = filename
            except Exception as e:
                print(f"[BluetoothListener] Error saving open step image: {e}")
                
        # Sub-steps check (Canned steps)
        for sub_step in step.get("sub_steps", []):
            facial = sub_step.get("facial", "")
            img_filename = sub_step.get("image_filename")
            
            # Find filename from facial tag if missing in sub_step
            if not img_filename and "[image:" in facial:
                match = re.search(r"\[image:(.+?)\]", facial)
                if match:
                    img_filename = match.group(1)
                    
            if img_filename and img_filename in images_dict:
                filename = os.path.basename(img_filename)
                local_path = os.path.join(images_dir, filename)
                try:
                    print(f"[BluetoothListener] Saving sub_step base64 image: {filename} -> {local_path}")
                    img_data = base64.b64decode(images_dict[img_filename])
                    with open(local_path, "wb") as f:
                        f.write(img_data)
                    # Update references in JSON
                    sub_step["image_filename"] = filename
                    sub_step["image_path"] = f"images/{filename}"
                except Exception as e:
                    print(f"[BluetoothListener] Error saving sub_step image: {e}")

def process_command_line(line):
    # Try to parse line as JSON command first
    command = None
    target_name = None
    msg = None
    
    try:
        msg = json.loads(line)
        if isinstance(msg, dict):
            command = msg.get("command")
            target_name = msg.get("name")
    except json.JSONDecodeError:
        pass
        
    # Standard text parsing fallback
    if command is None:
        parts = line.split(None, 1)
        if len(parts) > 0:
            first_word = parts[0].lower()
            if first_word in ["run", "stop", "status", "list", "exit"]:
                command = first_word
                if len(parts) > 1:
                    target_name = parts[1].strip()
            else:
                # Treat entire line as "run <script_name>"
                command = "run"
                target_name = line.strip()
        else:
            return

    # Execute Parsed Command
    command = command.lower()
    print(f"[BluetoothListener] Processing command '{command}' with arg '{target_name}'")

    if command == "run":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing script name. Usage: run <script_name>"
            })
            return
            
        script_info, error_details = find_script(target_name)
        if error_details:
            send_to_active_client(error_details)
            return
            
        success, res = execution_manager.start_script(script_info, handle_completion_callback)
        if success:
            send_to_active_client({
                "status": "starting",
                "message": f"Successfully started '{script_info['filename']}'",
                "name": script_info["filename"],
                "type": script_info["type"],
                "pid": res["pid"]
            })
        else:
            send_to_active_client({
                "status": "error",
                "message": res
            })

    elif command == "stop":
        success, msg = execution_manager.stop_current()
        try:
            base_dir = get_base_dir()
            movement_script = os.path.join(base_dir, "Character", "movement.py")
            subprocess.Popen([sys.executable, movement_script, "release"], cwd=os.path.dirname(movement_script))
            print("[BluetoothListener] Dispatched movement.py release subprocess to return home and release motors.")
        except Exception as e:
            print(f"[BluetoothListener] Error dispatching movement.py: {e}")
            
        send_to_active_client({
            "status": "stopped" if success else "error",
            "message": msg
        })

    elif command == "status":
        status_info = execution_manager.get_status()
        send_to_active_client({
            "status": "status",
            "running": status_info["running"],
            "name": status_info["name"],
            "type": status_info["type"],
            "pid": status_info["pid"]
        })

    elif command == "list":
        demos, scripts, zhennan = scan_files()
        plans = scan_activity_plans()
        interactions = scan_custom_interactions()
        send_to_active_client({
            "status": "list",
            "available_demos": sorted([info["filename"] for info in demos.values()]),
            "available_scripts": sorted([info["filename"] for info in scripts.values()]),
            "available_zhennan": sorted([info["filename"] for info in zhennan.values()]),
            "available_activity_plans": plans,
            "available_custom_interactions": interactions
        })

    elif command == "save_plan":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing plan folder name. Specify 'name'."
            })
            return
            
        plan_data = msg.get("plan") if isinstance(msg, dict) else None
        images_dict = msg.get("images") if isinstance(msg, dict) else None
        
        if not plan_data:
            send_to_active_client({
                "status": "error",
                "message": "Missing plan content in 'plan' field."
            })
            return
            
        try:
            base_dir = get_base_dir()
            folder_name = os.path.basename(target_name)
            if not folder_name.startswith("activity_plan_"):
                folder_name = "activity_plan_" + folder_name
                
            plan_dir = os.path.join(base_dir, "Assets", folder_name)
            os.makedirs(plan_dir, exist_ok=True)
            
            plan_file = os.path.join(plan_dir, "activity_plan.json")
            # Save any base64 images passed in the payload
            try:
                save_plan_images(plan_data, plan_dir, images_dict)
            except Exception as save_err:
                print(f"[BluetoothListener] Image save warning: {save_err}")
                
            with open(plan_file, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2)
                
            send_to_active_client({
                "status": "success",
                "message": f"Successfully saved activity plan to '{folder_name}'",
                "folder": folder_name
            })
        except Exception as e:
            send_to_active_client({
                "status": "error",
                "message": f"Failed to save plan: {str(e)}"
            })

    elif command == "save_custom_interaction":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing interaction folder name. Specify 'name'."
            })
            return
            
        interaction_data = msg.get("interaction") if isinstance(msg, dict) else None
        images_dict = msg.get("images") if isinstance(msg, dict) else None
        
        if not interaction_data:
            send_to_active_client({
                "status": "error",
                "message": "Missing interaction content in 'interaction' field."
            })
            return
            
        try:
            base_dir = get_base_dir()
            folder_name = os.path.basename(target_name)
            if not folder_name.startswith("custom_interaction_"):
                folder_name = "custom_interaction_" + folder_name
                
            interaction_dir = os.path.join(base_dir, "Assets", folder_name)
            os.makedirs(interaction_dir, exist_ok=True)
            
            interaction_file = os.path.join(interaction_dir, "custom_interaction.json")
            # Save any base64 images passed in the payload (reused save_plan_images helper)
            try:
                if images_dict:
                    save_plan_images(interaction_data, interaction_dir, images_dict)
            except Exception as save_err:
                print(f"[BluetoothListener] Image save warning: {save_err}")
                
            with open(interaction_file, "w", encoding="utf-8") as f:
                json.dump(interaction_data, f, indent=2)
                
            send_to_active_client({
                "status": "success",
                "message": f"Successfully saved custom interaction to '{folder_name}'",
                "folder": folder_name
            })
        except Exception as e:
            send_to_active_client({
                "status": "error",
                "message": f"Failed to save custom interaction: {str(e)}"
            })

    elif command == "exit":
        send_to_active_client({
            "status": "exiting",
            "message": "Goodbye!"
        })
        global active_client
        with active_client_lock:
            if active_client:
                active_client.close()

    else:
        send_to_active_client({
            "status": "error",
            "message": f"Unknown command: {command}"
        })

def tcp_listener_loop(port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("0.0.0.0", port))
        server_sock.listen(5)
        print(f"[BluetoothListener] TCP Fallback server listening on 0.0.0.0:{port}")
    except Exception as e:
        print(f"[BluetoothListener] Failed to start TCP fallback server: {e}")
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[BluetoothListener] TCP connection accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False)
            t = threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True)
            t.start()
        except Exception as e:
            print(f"[BluetoothListener] TCP accept error: {e}")
            time.sleep(1.0)

def bluetooth_rfcomm_listener_loop(channel):
    if not hasattr(socket, 'AF_BLUETOOTH'):
        print("[BluetoothListener] AF_BLUETOOTH not supported on this platform.")
        return

    server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        server_sock.bind(("", channel))
        server_sock.listen(1)
        print(f"[BluetoothListener] Classical Bluetooth RFCOMM server listening on channel {channel}")
    except Exception as e:
        print(f"[BluetoothListener] Failed to bind Bluetooth RFCOMM socket: {e}")
        server_sock.close()
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[BluetoothListener] Bluetooth RFCOMM connection accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False)
            t = threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True)
            t.start()
        except Exception as e:
            print(f"[BluetoothListener] Bluetooth RFCOMM accept error: {e}")
            time.sleep(1.0)

def is_rfcomm_connected(port_name):
    base_name = os.path.basename(port_name)
    try:
        res = subprocess.run(["rfcomm", "-a"], capture_output=True, text=True)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if base_name in line and "connected" in line.lower():
                    return True
    except Exception:
        pass
    return False

def serial_listener_loop(port_name):
    try:
        import serial
    except ImportError:
        print("[BluetoothListener] pyserial not installed. Skipping serial listener.")
        return

    print(f"[BluetoothListener] Starting Serial listener on port {port_name}...")
    is_rfcomm = "rfcomm" in port_name and sys.platform.startswith("linux")

    while True:
        try:
            if is_rfcomm:
                # Wait until rfcomm -a shows the port is actually connected
                if not is_rfcomm_connected(port_name):
                    time.sleep(1.0)
                    continue

            # Open serial port
            # Using timeout=1 and baudrate 115200
            with serial.Serial(port_name, baudrate=115200, timeout=1) as ser:
                print(f"[BluetoothListener] Serial port {port_name} opened. Waiting for connection...")
                wrapper = ConnectionWrapper(ser, is_serial=True, port_name=port_name)
                # Handle client in blocking way (since serial port is unique and holds lock)
                handle_client_connection(wrapper)
            # Sleep 2 seconds after connection terminates to prevent tight looping/spinning
            time.sleep(2.0)
        except Exception as e:
            # Port might not exist or busy, retry after delay
            time.sleep(2.0)

def websocket_listener_loop(port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("0.0.0.0", port))
        server_sock.listen(5)
        print(f"[BluetoothListener] WebSocket server listening on ws://0.0.0.0:{port}")
    except Exception as e:
        print(f"[BluetoothListener] Failed to start WebSocket server: {e}")
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[BluetoothListener] WebSocket connection accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False, is_websocket=True)
            t = threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True)
            t.start()
        except Exception as e:
            print(f"[BluetoothListener] WebSocket accept error: {e}")
            time.sleep(1.0)


def main():
    global execution_manager
    parser = argparse.ArgumentParser(description="Gigi Bluetooth Script & Demo Interface Listener")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_TCP_PORT, help="Port for TCP fallback listener")
    parser.add_argument("--rfcomm-channel", type=int, default=DEFAULT_RFCOMM_CHANNEL, help="RFCOMM channel for direct Bluetooth socket")
    parser.add_argument("--serial-port", type=str, default=None, help="Serial/COM port name (e.g. COM4 or /dev/rfcomm0) for SPP")
    args = parser.parse_args()

    print("="*60)
    print("      Gigi Bluetooth Script/Demo Runner Interface")
    print("="*60)

    # Initialize subprocess execution manager
    execution_manager = ExecutionManager()

    # Register SDP Serial Port profile on Linux
    if sys.platform.startswith("linux"):
        print("[BluetoothListener] Registering Bluetooth SPP profile via sdptool...")
        try:
            subprocess.run(["sudo", "sdptool", "add", "SP"], stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[BluetoothListener] Failed to register SPP profile: {e}")

    # Launch parallel listener threads
    threads = []
    
    # 1. TCP Fallback Listener
    tcp_thread = threading.Thread(target=tcp_listener_loop, args=(args.tcp_port,), daemon=True)
    tcp_thread.start()
    threads.append(tcp_thread)

    # 4. WebSocket Listener (Port 5007)
    ws_thread = threading.Thread(target=websocket_listener_loop, args=(5007,), daemon=True)
    ws_thread.start()
    threads.append(ws_thread)

    # 2. Native Bluetooth RFCOMM Socket Listener
    bt_thread = threading.Thread(target=bluetooth_rfcomm_listener_loop, args=(args.rfcomm_channel,), daemon=True)
    bt_thread.start()
    threads.append(bt_thread)

    # 3. Optional Serial/COM Port Listener (SPP)
    serial_port = args.serial_port
    if not serial_port and sys.platform.startswith("linux"):
        serial_port = "/dev/rfcomm0"

    if serial_port:
        serial_thread = threading.Thread(target=serial_listener_loop, args=(serial_port,), daemon=True)
        serial_thread.start()
        threads.append(serial_thread)

    try:
        # Keep main thread alive
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[BluetoothListener] Shutting down interface...")

if __name__ == "__main__":
    main()
