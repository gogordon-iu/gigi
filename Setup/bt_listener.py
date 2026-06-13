#!/usr/bin/env python3
import os
import sys
import json
import time
import socket
import threading
import subprocess
import argparse

# Configuration
DEFAULT_TCP_PORT = 5006
DEFAULT_RFCOMM_CHANNEL = 1

# Global state
execution_manager = None
active_client = None
active_client_lock = threading.Lock()

def get_base_dir():
    # Since this file resides in gigi/Setup/bt_listener.py, base_dir is gigi/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def scan_files():
    """
    Scans the Demo/ and Scripts/ directories for executable Python files.
    Returns:
        demos (dict): lowercase stem -> file info dict
        scripts (dict): lowercase stem -> file info dict
    """
    base_dir = get_base_dir()
    demo_dir = os.path.join(base_dir, "Demo")
    scripts_dir = os.path.join(base_dir, "Scripts")
    
    demos = {}
    scripts = {}
    
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
                
    return demos, scripts

def find_script(target_name):
    """
    Looks up a script or demo by its name or filename.
    Returns:
        (script_info, error_details)
    """
    demos, scripts = scan_files()
    
    # Strip extension if present
    clean_name = target_name.strip()
    if clean_name.lower().endswith(".py"):
        clean_name = clean_name[:-3]
        
    key = clean_name.lower()
    
    if key in demos:
        return demos[key], None
    if key in scripts:
        return scripts[key], None
        
    # No match found. Construct a detailed error report.
    available_demos = [info["filename"] for info in demos.values()]
    available_scripts = [info["filename"] for info in scripts.values()]
    
    err_msg = f"Script or demo '{target_name}' not found."
    error_details = {
        "status": "error",
        "error": "not_found",
        "message": err_msg,
        "requested": target_name,
        "available_demos": sorted(available_demos),
        "available_scripts": sorted(available_scripts)
    }
    return None, error_details

class ConnectionWrapper:
    """
    A wrapper class to unify socket and serial interfaces for reading/writing.
    """
    def __init__(self, conn_obj, is_serial=False):
        self.conn = conn_obj
        self.is_serial = is_serial
        self.closed = False

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
                    time.sleep(0.05)
                return b""
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
                # Run subprocess using system Python executable
                self.process = subprocess.Popen(
                    [sys.executable, script_info["path"]],
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

def process_command_line(line):
    # Try to parse line as JSON command first
    command = None
    target_name = None
    
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
        demos, scripts = scan_files()
        send_to_active_client({
            "status": "list",
            "available_demos": sorted([info["filename"] for info in demos.values()]),
            "available_scripts": sorted([info["filename"] for info in scripts.values()])
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

def serial_listener_loop(port_name):
    try:
        import serial
    except ImportError:
        print("[BluetoothListener] pyserial not installed. Skipping serial listener.")
        return

    print(f"[BluetoothListener] Starting Serial listener on port {port_name}...")
    while True:
        try:
            # Open serial port
            # Using timeout=1 and baudrate 115200
            with serial.Serial(port_name, baudrate=115200, timeout=1) as ser:
                print(f"[BluetoothListener] Serial port {port_name} opened. Waiting for connection...")
                wrapper = ConnectionWrapper(ser, is_serial=True)
                # Handle client in blocking way (since serial port is unique and holds lock)
                handle_client_connection(wrapper)
        except Exception as e:
            # Port might not exist or busy, retry after delay
            time.sleep(2.0)

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
