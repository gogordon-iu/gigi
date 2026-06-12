#!/usr/bin/env python3
import sys
import os
import subprocess
import threading
import time

PIN_CODE = "198420"

def read_output(process):
    print(f"[*] Started bluetoothctl monitor thread. Auto-confirm PIN is: {PIN_CODE}")
    try:
        # Read stdout line by line
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            line_str = line.strip()
            print(f"[bluetoothctl] {line_str}")
            
            # Auto-respond to pairing requests
            lower_line = line_str.lower()
            
            # Confirm passkey (Numeric comparison)
            if "confirm passkey" in lower_line and "(yes/no)" in lower_line:
                print(f"[*] Auto-confirming passkey confirmation request...")
                process.stdin.write("yes\n")
                process.stdin.flush()
                
            # Request PIN code
            elif "request pin code" in lower_line or "enter pin code" in lower_line:
                print(f"[*] Sending PIN code {PIN_CODE}...")
                process.stdin.write(f"{PIN_CODE}\n")
                process.stdin.flush()
                
            # Request Passkey
            elif "request passkey" in lower_line or "enter passkey" in lower_line:
                print(f"[*] Sending passkey {PIN_CODE}...")
                process.stdin.write(f"{PIN_CODE}\n")
                process.stdin.flush()
                
            # Authorize service or connection
            elif "authorize service" in lower_line or "authorize connection" in lower_line:
                print(f"[*] Authorizing service request...")
                process.stdin.write("yes\n")
                process.stdin.flush()
                
    except Exception as e:
        print(f"[!] Error in monitor thread: {e}")

def main():
    print("="*60)
    print("      Gigi Headless Auto-Pairing Bluetooth Agent")
    print("="*60)
    
    # Run bluetoothctl under sudo to register agents on Linux
    cmd = ["sudo", "bluetoothctl"]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    except Exception as e:
        print(f"[!] Failed to launch bluetoothctl: {e}")
        sys.exit(1)
        
    # Start monitor thread
    monitor_thread = threading.Thread(target=read_output, args=(process,), daemon=True)
    monitor_thread.start()
    
    # Initialize agent configuration
    time.sleep(1.0)
    print("[*] Initializing adapter configuration...")
    
    commands = [
        "power on",
        "discoverable on",
        "pairable on",
        "agent KeyboardOnly",
        "default-agent"
    ]
    
    for cmd in commands:
        process.stdin.write(f"{cmd}\n")
        process.stdin.flush()
        time.sleep(0.5)
        
    print("[*] Agent is running in the background. Press Ctrl+C to terminate.")
    
    try:
        while True:
            time.sleep(1.0)
            if process.poll() is not None:
                print("[!] bluetoothctl process terminated.")
                break
    except KeyboardInterrupt:
        print("\n[*] Shutting down Agent...")
    finally:
        try:
            process.stdin.write("exit\n")
            process.stdin.flush()
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    main()
