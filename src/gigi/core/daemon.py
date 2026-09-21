#!/usr/bin/env python3
"""
Gigi Background Daemon Service.
Provides multi-transport connectivity (WebSocket, TCP socket, Bluetooth RFCOMM, and Serial SPP)
for the Gigi Mobile & Web apps, managing activity lifecycles, script execution, speech pregeneration,
and motor calibration safety lockouts.
"""

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
import logging

from gigi.core.config import (
    PROJECT_ROOT,
    ASSETS_DIR,
    DEFAULT_TCP_PORT,
    DEFAULT_RFCOMM_CHANNEL,
)

logger = logging.getLogger("gigi.daemon")

# Global state
execution_manager = None
active_client = None
active_client_lock = threading.Lock()


# --- WebSocket Protocol Helpers ---

def parse_websocket_handshake(headers_str):
    key = None
    for line in headers_str.split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
            break
    if not key:
        return None
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    accept_key = base64.b64encode(hashlib.sha1((key + guid).encode('utf-8')).digest()).decode('utf-8')
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
        if len(data) < 4:
            return 0
        actual_len = struct.unpack("!H", data[2:4])[0]
    elif payload_len == 127:
        if len(data) < 10:
            return 0
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
        mask_key = data[offset:offset + 4]
        offset += 4
    else:
        mask_key = None

    if len(data) < offset + payload_len:
        return None, b""

    payload = data[offset:offset + payload_len]

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


# --- File and Activity Scanners ---

def scan_custom_interactions():
    """
    Scans the Assets/ directory for subdirectories starting with 'custom_interaction_'.
    Returns a list of dicts: [{"folder": folder_name, "title": interaction_title}]
    """
    assets_dir = str(ASSETS_DIR)
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
                interactions.append({"folder": entry, "title": title})
    return interactions


def scan_activity_plans():
    """
    Scans the Assets/ directory for subdirectories starting with 'activity_plan_'.
    Returns a list of dicts: [{"folder": folder_name, "title": activity_title}]
    """
    assets_dir = str(ASSETS_DIR)
    plans = []
    if os.path.isdir(assets_dir):
        for entry in os.listdir(assets_dir):
            entry_path = os.path.join(assets_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("activity_plan_"):
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
                plans.append({"folder": entry, "title": title})
    return plans


def scan_files():
    """
    Scans src/gigi/activities/ and src/gigi/interaction/ for executable activities and scripts.
    """
    base_dir = str(PROJECT_ROOT)
    activities_dir = os.path.join(base_dir, "src", "gigi", "activities")
    interaction_dir = os.path.join(base_dir, "src", "gigi", "interaction")

    demos = {}
    scripts = {}
    zhennan = {}

    # 1. Scan activities in src/gigi/activities/
    if os.path.isdir(activities_dir):
        for root, dirs, files in os.walk(activities_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "common"]
            for f in files:
                if f.endswith(".py") and f != "__init__.py" and f != "base.py" and not f.startswith("test_"):
                    stem = os.path.splitext(f)[0]
                    is_scripted = "scripted" in root
                    if is_scripted and stem not in ["ferris", "halloween", "lego"]:
                        continue

                    file_type = "script" if is_scripted else "demo"
                    info = {
                        "filename": f,
                        "stem": stem,
                        "path": os.path.abspath(os.path.join(root, f)),
                        "dir": os.path.abspath(root),
                        "type": file_type,
                    }
                    demos[stem.lower()] = info
                    if is_scripted:
                        scripts[stem.lower()] = info

    # 2. Add interaction runners
    runner_path = os.path.join(interaction_dir, "runner.py")
    if os.path.isfile(runner_path):
        runner_info = {
            "filename": "runner.py",
            "stem": "runner",
            "path": os.path.abspath(runner_path),
            "dir": os.path.abspath(interaction_dir),
            "type": "script",
        }
        zhennan["run_activity_teacherdemo"] = dict(
            runner_info, filename="run_activity_teacherdemo.py", stem="run_activity_teacherdemo"
        )
        zhennan["runner"] = runner_info

    custom_runner_path = os.path.join(interaction_dir, "custom_runner.py")
    if os.path.isfile(custom_runner_path):
        custom_info = {
            "filename": "custom_runner.py",
            "stem": "custom_runner",
            "path": os.path.abspath(custom_runner_path),
            "dir": os.path.abspath(interaction_dir),
            "type": "script",
        }
        zhennan["run_custom_interaction"] = dict(
            custom_info, filename="run_custom_interaction.py", stem="run_custom_interaction"
        )
        zhennan["custom_runner"] = custom_info

    # 3. Add motor calibration wizard
    calib_path = os.path.join(base_dir, "src", "gigi", "verification", "hardware", "calibrate_motors.py")
    if os.path.isfile(calib_path):
        calib_info = {
            "filename": "calibrate_motors.py",
            "stem": "calibrate_motors",
            "path": os.path.abspath(calib_path),
            "dir": os.path.abspath(os.path.dirname(calib_path)),
            "type": "demo",
        }
        demos["calibrate_motors"] = calib_info
        demos["calibrate"] = calib_info
        demos["motor_calibration"] = calib_info

    # 4. Add aliases for common historical names
    aliases = {
        "readingfluencydemo": "reading_fluency",
        "readingfluency": "reading_fluency",
        "reading_fluency_demo": "reading_fluency",
        "mastermind_game": "mastermind",
        "mathquest": "math_quest",
        "storyquest": "story_game",
        "make_friends_demo": "make_friends",
        "makefriends": "make_friends",
        "alivemode": "alive_mode",
        "alive_mode_demo": "alive_mode",
        "face_demo": "face_recognition_demo",
        "calibrate": "calibrate_motors",
        "calibrate_motors": "calibrate_motors",
        "motor_calibration": "calibrate_motors",
    }
    for alias, target in aliases.items():
        if target in demos and alias not in demos:
            demos[alias] = demos[target]

    return demos, scripts, zhennan


def find_script(target_name):
    """
    Looks up an activity, script, demo, or interaction runner by its name or filename.
    """
    demos, scripts, zhennan = scan_files()

    if target_name.startswith("activity_plan_"):
        teacher_script_key = "run_activity_teacherdemo"
        if teacher_script_key in zhennan:
            info = dict(zhennan[teacher_script_key])
            info["args"] = [target_name]
            info["filename"] = f"{info['filename']} ({target_name})"
            return info, None

    if target_name.startswith("custom_interaction_"):
        custom_script_key = "run_custom_interaction"
        if custom_script_key in zhennan:
            info = dict(zhennan[custom_script_key])
            info["args"] = [target_name]
            info["filename"] = f"{info['filename']} ({target_name})"
            return info, None

    clean_name = target_name.strip()
    if clean_name.lower().endswith(".py"):
        clean_name = clean_name[:-3]

    key = clean_name.lower().replace("-", "_").replace(" ", "_")

    if key in demos:
        return demos[key], None
    if key in scripts:
        return scripts[key], None
    if key in zhennan:
        return zhennan[key], None

    available_demos = [info["filename"] for info in demos.values()]
    available_scripts = [info["filename"] for info in scripts.values()]
    available_zhennan = [info["filename"] for info in zhennan.values()]

    err_msg = f"Script, activity, or demo '{target_name}' not found."
    error_details = {
        "status": "error",
        "error": "not_found",
        "message": err_msg,
        "requested": target_name,
        "available_demos": sorted(list(set(available_demos))),
        "available_scripts": sorted(list(set(available_scripts))),
        "available_zhennan": sorted(list(set(available_zhennan))),
    }
    return None, error_details


class ConnectionWrapper:
    """
    Unifies socket, serial, and websocket interfaces for bidirectional streaming.
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
                while not self.closed:
                    data = self.conn.read(limit)
                    if data:
                        return data
                    if self.port_name and "rfcomm" in self.port_name:
                        if not is_rfcomm_connected(self.port_name):
                            self.closed = True
                            break
                    time.sleep(0.05)
                return b""
            elif self.is_websocket:
                if not self.handshake_done:
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
                            return b""
                        else:
                            self.closed = True
                            return b""
                    else:
                        self.closed = True
                        return b""

                data = self.conn.recv(limit)
                if not data:
                    self.closed = True
                    return b""
                self.websocket_buffer += data

                msg_type, payload = decode_websocket_frame(self.websocket_buffer)
                if msg_type == "close":
                    self.closed = True
                    return b""
                elif msg_type is None:
                    return b""

                frame_len = get_websocket_frame_length(self.websocket_buffer)
                if frame_len > 0:
                    self.websocket_buffer = self.websocket_buffer[frame_len:]
                return payload
            else:
                data = self.conn.recv(limit)
                return data
        except Exception as e:
            print(f"[ConnectionWrapper] Recv error: {e}")
            self.closed = True
            return b""

    def sendall(self, data):
        if self.closed:
            return
        try:
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

            print(f"[ExecutionManager] Executing script '{self.process_name}' via subprocess...")
            try:
                cmd = [sys.executable, "-u", script_info["path"]]
                if "args" in script_info:
                    cmd.extend(script_info["args"])
                base_dir = str(PROJECT_ROOT)
                src_dir = os.path.join(base_dir, "src")
                sub_env = dict(os.environ)
                if "PYTHONPATH" in sub_env:
                    sub_env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{sub_env['PYTHONPATH']}"
                else:
                    sub_env["PYTHONPATH"] = src_dir

                self.process = subprocess.Popen(
                    cmd,
                    cwd=script_info["dir"],
                    env=sub_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    bufsize=1,
                )
            except Exception as e:
                return False, f"Failed to launch script: {e}"

            self.monitor_thread = threading.Thread(
                target=self._monitor_lifecycle,
                args=(self.process, self.process_name, self.process_type),
                daemon=True,
            )
            self.monitor_thread.start()
            return True, {
                "pid": self.process.pid,
                "name": self.process_name,
                "type": self.process_type,
            }

    def stop_current(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                name = self.process_name
                print(f"[ExecutionManager] Terminating script '{name}' (PID {self.process.pid})...")
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
                    "pid": self.process.pid,
                }
            return {
                "running": False,
                "name": None,
                "type": None,
                "pid": None,
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


execution_manager = ExecutionManager()


def send_to_active_client(msg_dict):
    global active_client
    with active_client_lock:
        if active_client:
            try:
                payload = (json.dumps(msg_dict) + "\n").encode('utf-8')
                active_client.sendall(payload)
            except Exception as e:
                print(f"[Daemon] Error sending to active client: {e}")
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
        "message": f"Script '{name}' finished with return code {return_code}",
    })


def save_plan_images(plan, plan_dir, images_dict):
    import re
    images_dir = os.path.join(plan_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    if not images_dict:
        images_dict = {}

    for step in plan.get("steps", []):
        img_filename = step.get("image_filename")
        if img_filename and img_filename in images_dict:
            filename = os.path.basename(img_filename)
            local_path = os.path.join(images_dir, filename)
            try:
                img_data = base64.b64decode(images_dict[img_filename])
                with open(local_path, "wb") as f:
                    f.write(img_data)
                step["image_path"] = f"images/{filename}"
                step["image_filename"] = filename
            except Exception as e:
                print(f"[Daemon] Error saving step image: {e}")

        if "image_url" in step and isinstance(step["image_url"], str) and step["image_url"].startswith("data:"):
            step["image_url"] = step.get("image_path", step.get("image_filename", ""))

        for sub_step in step.get("sub_steps", []):
            facial = sub_step.get("facial", "")
            img_sub = sub_step.get("image_filename")
            if not img_sub and "[image:" in facial:
                match = re.search(r"\[image:(.+?)\]", facial)
                if match:
                    img_sub = match.group(1)

            if img_sub and img_sub in images_dict:
                filename = os.path.basename(img_sub)
                local_path = os.path.join(images_dir, filename)
                try:
                    img_data = base64.b64decode(images_dict[img_sub])
                    with open(local_path, "wb") as f:
                        f.write(img_data)
                    sub_step["image_filename"] = filename
                    sub_step["image_path"] = f"images/{filename}"
                except Exception as e:
                    print(f"[Daemon] Error saving sub-step image: {e}")

            if "image_url" in sub_step and isinstance(sub_step["image_url"], str) and sub_step["image_url"].startswith("data:"):
                sub_step["image_url"] = sub_step.get("image_path", sub_step.get("image_filename", ""))


def pregenerate_activity_speech(plan_data, activity_folder):
    try:
        print(f"[SpeechPregen] Extracting text to pregenerate for activity '{activity_folder}'...")
        texts_to_generate = []
        steps = plan_data.get("steps", plan_data.get("phases", []))
        for step in steps:
            sub_steps = step.get("sub_steps", [])
            for sub in sub_steps:
                if isinstance(sub, dict) and "text" in sub:
                    txt = sub["text"].strip()
                    if txt:
                        texts_to_generate.append(txt)
            if "text" in step and isinstance(step["text"], str):
                txt = step["text"].strip()
                if txt:
                    texts_to_generate.append(txt)

        if not texts_to_generate:
            return

        import re
        from gigi.expression.speech import Speech

        speech_engine = Speech(activity=activity_folder)
        for txt in texts_to_generate:
            try:
                clean_txt = re.sub(r'\[.*?\]', '', txt).strip()
                clean_txt = re.sub(r'\s+', ' ', clean_txt)
                sentences = re.split(r'(?<=[.!?])\s+', clean_txt)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        speech_engine.update_audio_objects(text=sentence)
            except Exception as gen_err:
                print(f"[SpeechPregen] Error generating speech: {gen_err}")

        del speech_engine
        import gc
        gc.collect()
        print("[SpeechPregen] Speech pregeneration complete.")
    except Exception as e:
        print(f"[SpeechPregen] Failed to pregenerate speech: {e}")


def process_command_line(line):
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

    if command is None:
        parts = line.split(None, 1)
        if len(parts) > 0:
            first_word = parts[0].lower()
            if first_word in ["run", "stop", "status", "list", "exit", "calibrate"]:
                command = first_word
                if len(parts) > 1:
                    target_name = parts[1].strip()
            else:
                command = "run"
                target_name = line.strip()
        else:
            return

    command = command.lower()
    print(f"[Daemon] Processing command '{command}' with arg '{target_name}'")

    if command == "run":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing script name. Usage: run <script_name>",
            })
            return

        from gigi.hardware.calibration import is_motor_calibrated
        is_calib_target = target_name.lower().replace(".py", "").replace("_", "").replace(" ", "") in [
            "calibrate", "calibratemotors", "motorcalibration"
        ]
        if not is_motor_calibrated() and not is_calib_target:
            send_to_active_client({
                "status": "error",
                "error": "uncalibrated",
                "message": "Physical motors are UNCALIBRATED! Movement is locked for safety. Please run motor calibration first.",
                "requires_calibration": True,
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
                "pid": res["pid"],
            })
        else:
            send_to_active_client({
                "status": "error",
                "message": res,
            })

    elif command == "calibrate":
        script_info, error_details = find_script("calibrate_motors")
        if error_details:
            send_to_active_client(error_details)
            return

        success, res = execution_manager.start_script(script_info, handle_completion_callback)
        if success:
            send_to_active_client({
                "status": "starting",
                "message": "Starting interactive motor calibration wizard...",
                "name": script_info["filename"],
                "type": script_info["type"],
                "pid": res["pid"],
            })
        else:
            send_to_active_client({
                "status": "error",
                "message": res,
            })

    elif command == "stop":
        success, msg = execution_manager.stop_current()
        try:
            base_dir = str(PROJECT_ROOT)
            src_dir = os.path.join(base_dir, "src")
            sub_env = dict(os.environ)
            if "PYTHONPATH" in sub_env:
                sub_env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{sub_env['PYTHONPATH']}"
            else:
                sub_env["PYTHONPATH"] = src_dir

            subprocess.Popen(
                [sys.executable, "-m", "gigi.expression.movement", "release"],
                cwd=base_dir,
                env=sub_env,
            )
        except Exception as e:
            print(f"[Daemon] Error dispatching movement release: {e}")

        send_to_active_client({
            "status": "stopped" if success else "error",
            "message": msg,
        })

    elif command == "status":
        status_info = execution_manager.get_status()
        from gigi.hardware.calibration import is_motor_calibrated
        send_to_active_client({
            "status": "status",
            "running": status_info["running"],
            "name": status_info["name"],
            "type": status_info["type"],
            "pid": status_info["pid"],
            "calibrated": is_motor_calibrated(),
        })

    elif command == "list":
        demos, scripts, zhennan = scan_files()
        plans = scan_activity_plans()
        interactions = scan_custom_interactions()
        from gigi.hardware.calibration import is_motor_calibrated
        activities_dir = os.path.join(str(PROJECT_ROOT), "src", "gigi", "activities")
        categorized_activities = []
        for info in sorted(demos.values(), key=lambda x: x["stem"]):
            stem = info["stem"]
            rel_dir = os.path.relpath(info["dir"], activities_dir).replace("\\", "/")
            subcat = rel_dir.split("/")[0] if rel_dir != "." else "general"
            categorized_activities.append({
                "name": info["filename"],
                "stem": stem,
                "type": "core",
                "category": subcat,
                "module": f"gigi.activities.{subcat}.{stem}" if subcat != "general" else f"gigi.activities.{stem}",
            })
        send_to_active_client({
            "status": "list",
            "available_demos": sorted([info["filename"] for info in demos.values()]),
            "available_scripts": sorted([info["filename"] for info in scripts.values()]),
            "available_zhennan": sorted([info["filename"] for info in zhennan.values()]),
            "available_activity_plans": plans,
            "available_custom_interactions": interactions,
            "categorized_activities": categorized_activities,
            "calibrated": is_motor_calibrated(),
        })

    elif command == "save_plan":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing plan folder name.",
            })
            return

        plan_data = msg.get("plan") if isinstance(msg, dict) else None
        images_dict = msg.get("images") if isinstance(msg, dict) else None

        if not plan_data:
            send_to_active_client({
                "status": "error",
                "message": "Missing plan content.",
            })
            return

        try:
            folder_name = os.path.basename(target_name)
            if not folder_name.startswith("activity_plan_"):
                folder_name = "activity_plan_" + folder_name

            plan_dir = os.path.join(str(ASSETS_DIR), folder_name)
            os.makedirs(plan_dir, exist_ok=True)
            plan_file = os.path.join(plan_dir, "activity_plan.json")

            try:
                save_plan_images(plan_data, plan_dir, images_dict)
            except Exception as save_err:
                print(f"[Daemon] Image save warning: {save_err}")

            with open(plan_file, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=2)

            threading.Thread(
                target=pregenerate_activity_speech,
                args=(plan_data, folder_name),
                daemon=True,
            ).start()

            send_to_active_client({
                "status": "success",
                "message": f"Successfully saved activity plan to '{folder_name}'",
                "folder": folder_name,
            })
        except Exception as e:
            send_to_active_client({
                "status": "error",
                "message": f"Failed to save plan: {str(e)}",
            })

    elif command == "save_custom_interaction":
        if not target_name:
            send_to_active_client({
                "status": "error",
                "message": "Missing interaction folder name.",
            })
            return

        interaction_data = msg.get("interaction") if isinstance(msg, dict) else None
        images_dict = msg.get("images") if isinstance(msg, dict) else None

        if not interaction_data:
            send_to_active_client({
                "status": "error",
                "message": "Missing interaction content.",
            })
            return

        try:
            folder_name = os.path.basename(target_name)
            if not folder_name.startswith("custom_interaction_"):
                folder_name = "custom_interaction_" + folder_name

            interaction_dir = os.path.join(str(ASSETS_DIR), folder_name)
            os.makedirs(interaction_dir, exist_ok=True)
            interaction_file = os.path.join(interaction_dir, "custom_interaction.json")

            if images_dict:
                save_plan_images(interaction_data, interaction_dir, images_dict)

            with open(interaction_file, "w", encoding="utf-8") as f:
                json.dump(interaction_data, f, indent=2)

            send_to_active_client({
                "status": "success",
                "message": f"Successfully saved custom interaction to '{folder_name}'",
                "folder": folder_name,
            })
        except Exception as e:
            send_to_active_client({
                "status": "error",
                "message": f"Failed to save custom interaction: {str(e)}",
            })

    elif command == "exit":
        send_to_active_client({"status": "exiting", "message": "Goodbye!"})
        global active_client
        with active_client_lock:
            if active_client:
                active_client.close()

    else:
        send_to_active_client({"status": "error", "message": f"Unknown command: {command}"})


def handle_client_connection(client_wrapper):
    global active_client
    with active_client_lock:
        if active_client is not None:
            try:
                client_wrapper.sendall(json.dumps({
                    "status": "busy",
                    "message": "Another client is already connected to Gigi daemon.",
                }).encode('utf-8') + b"\n")
                client_wrapper.close()
            except Exception:
                pass
            return
        active_client = client_wrapper

    print("[Daemon] Active client connection established.")
    from gigi.hardware.calibration import is_motor_calibrated
    send_to_active_client({
        "status": "ready",
        "message": "Connected to Gigi daemon. Ready for commands.",
        "calibrated": is_motor_calibrated(),
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
                if line:
                    process_command_line(line)
    except Exception as e:
        print(f"[Daemon] Client connection handler error: {e}")
    finally:
        with active_client_lock:
            if active_client == client_wrapper:
                active_client = None
        client_wrapper.close()
        print("[Daemon] Client connection closed.")


def tcp_listener_loop(port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("0.0.0.0", port))
        server_sock.listen(5)
        print(f"[Daemon] TCP server listening on 0.0.0.0:{port}")
    except Exception as e:
        print(f"[Daemon] Failed to start TCP server: {e}")
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[Daemon] TCP connection accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False)
            threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True).start()
        except Exception as e:
            print(f"[Daemon] TCP accept error: {e}")
            time.sleep(1.0)


def websocket_listener_loop(port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("0.0.0.0", port))
        server_sock.listen(5)
        print(f"[Daemon] WebSocket server listening on ws://0.0.0.0:{port}")
    except Exception as e:
        print(f"[Daemon] Failed to start WebSocket server: {e}")
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[Daemon] WebSocket connection accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False, is_websocket=True)
            threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True).start()
        except Exception as e:
            print(f"[Daemon] WebSocket accept error: {e}")
            time.sleep(1.0)


def bluetooth_rfcomm_listener_loop(channel):
    if not hasattr(socket, 'AF_BLUETOOTH'):
        print("[Daemon] AF_BLUETOOTH not supported on this platform.")
        return

    server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        server_sock.bind(("", channel))
        server_sock.listen(1)
        print(f"[Daemon] Classical Bluetooth RFCOMM listening on channel {channel}")
    except Exception as e:
        print(f"[Daemon] Failed to bind Bluetooth RFCOMM socket: {e}")
        server_sock.close()
        return

    while True:
        try:
            conn, addr = server_sock.accept()
            print(f"[Daemon] Bluetooth RFCOMM accepted from {addr}")
            wrapper = ConnectionWrapper(conn, is_serial=False)
            threading.Thread(target=handle_client_connection, args=(wrapper,), daemon=True).start()
        except Exception as e:
            print(f"[Daemon] Bluetooth RFCOMM accept error: {e}")
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
        print("[Daemon] pyserial not installed. Skipping serial listener.")
        return

    print(f"[Daemon] Starting Serial listener on port {port_name}...")
    is_rfcomm = "rfcomm" in port_name and sys.platform.startswith("linux")

    while True:
        try:
            if is_rfcomm and not is_rfcomm_connected(port_name):
                time.sleep(1.0)
                continue

            with serial.Serial(port_name, baudrate=115200, timeout=1) as ser:
                print(f"[Daemon] Serial port {port_name} opened. Waiting for connection...")
                wrapper = ConnectionWrapper(ser, is_serial=True, port_name=port_name)
                handle_client_connection(wrapper)
            time.sleep(2.0)
        except Exception:
            time.sleep(2.0)


def main():
    global execution_manager
    parser = argparse.ArgumentParser(description="Gigi Robot Background Daemon Service")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_TCP_PORT, help="Port for TCP socket listener")
    parser.add_argument("--ws-port", type=int, default=5007, help="Port for WebSocket listener")
    parser.add_argument("--rfcomm-channel", type=int, default=DEFAULT_RFCOMM_CHANNEL, help="RFCOMM channel for Bluetooth socket")
    parser.add_argument("--serial-port", type=str, default=None, help="Serial/COM port name for SPP")
    args = parser.parse_args()

    print("=" * 60)
    print("      Gigi Social Robot Daemon Service")
    print("=" * 60)

    execution_manager = ExecutionManager()

    if sys.platform.startswith("linux"):
        try:
            subprocess.run(["sudo", "sdptool", "add", "SP"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # Launch parallel transports
    threading.Thread(target=tcp_listener_loop, args=(args.tcp_port,), daemon=True).start()
    threading.Thread(target=websocket_listener_loop, args=(args.ws_port,), daemon=True).start()
    threading.Thread(target=bluetooth_rfcomm_listener_loop, args=(args.rfcomm_channel,), daemon=True).start()

    serial_port = args.serial_port
    if not serial_port and sys.platform.startswith("linux"):
        serial_port = "/dev/rfcomm0"

    if serial_port:
        threading.Thread(target=serial_listener_loop, args=(serial_port,), daemon=True).start()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Daemon] Shutting down...")


if __name__ == "__main__":
    main()
