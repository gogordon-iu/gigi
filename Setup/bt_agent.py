#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import threading
import time

PIN_CODE = os.environ.get("GIGI_BT_PIN", "198420")


def read_output(process):
    print(f"[*] Started bluetoothctl monitor thread. Auto-confirm PIN is: {PIN_CODE}")
    buffer = b""
    line_buffer = b""
    trusted_macs = set()
    mac_pattern = re.compile(r"[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}")
    state_pattern = re.compile(r"\bpaired:\s+yes\b", re.IGNORECASE)

    try:
        while True:
            chunk = process.stdout.read(1)
            if not chunk:
                break

            # Print to stdout
            sys.stdout.write(chunk.decode('utf-8', errors='ignore'))
            sys.stdout.flush()

            # Trust only completed lines reporting a successfully paired device.
            # Use a separate process so trust commands cannot answer agent prompts.
            line_buffer += chunk
            if chunk in (b"\n", b"\r"):
                line_str = line_buffer.decode('utf-8', errors='ignore')
                if state_pattern.search(line_str):
                    mac_match = mac_pattern.search(line_str)
                    if mac_match:
                        mac = mac_match.group(0)
                        normalized_mac = mac.upper()
                        if normalized_mac not in trusted_macs:
                            subprocess.Popen(
                                ["sudo", "bluetoothctl", "trust", mac],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                            trusted_macs.add(normalized_mac)
                line_buffer = b""
            elif len(line_buffer) > 2000:
                line_buffer = line_buffer[-500:]

            buffer += chunk
            buffer_str = buffer.decode('utf-8', errors='ignore').lower()

            # Confirm passkey (Numeric comparison)
            if "confirm passkey" in buffer_str and "(yes/no):" in buffer_str:
                print(f"\n[*] Auto-confirming passkey confirmation request...")
                process.stdin.write(b"yes\n")
                process.stdin.flush()
                buffer = b""

            # Request PIN code
            elif "request pin code" in buffer_str or "enter pin code" in buffer_str:
                if ":" in buffer_str:
                    print(f"\n[*] Sending PIN code {PIN_CODE}...")
                    process.stdin.write(f"{PIN_CODE}\n".encode('utf-8'))
                    process.stdin.flush()
                    buffer = b""

            # Request Passkey
            elif "request passkey" in buffer_str or "enter passkey" in buffer_str:
                if ":" in buffer_str:
                    print(f"\n[*] Sending passkey {PIN_CODE}...")
                    process.stdin.write(f"{PIN_CODE}\n".encode('utf-8'))
                    process.stdin.flush()
                    buffer = b""

            # Auto-authorize any confirmation, passkey, or connection prompt
            elif "(yes/no):" in buffer_str:
                print(f"\n[*] Auto-authorizing yes/no request from bluetoothctl...")
                process.stdin.write(b"yes\n")
                process.stdin.flush()
                buffer = b""

            # Keep buffer size reasonable
            if len(buffer) > 2000:
                buffer = buffer[-500:]

    except Exception as e:
        print(f"\n[!] Error in monitor thread: {e}")


def main():
    print("="*60)
    print("      Gigi Headless Auto-Pairing Bluetooth Agent")
    print("="*60)

    # Register the desired agent at startup on BlueZ 5.64.
    # Use stdbuf to disable stdout/stderr buffering in bluetoothctl.
    cmd = [
        "sudo", "stdbuf", "-o0", "-e0", "bluetoothctl",
        "--agent", "NoInputNoOutput"
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0
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
        "system-alias orangepi5pro",
        "discoverable-timeout 0",
        "discoverable on",
        "pairable on",
        "default-agent",
        "devices"
    ]

    for cmd in commands:
        process.stdin.write(f"{cmd}\n".encode('utf-8'))
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
            process.stdin.write(b"exit\n")
            process.stdin.flush()
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            pass


if __name__ == "__main__":
    main()
