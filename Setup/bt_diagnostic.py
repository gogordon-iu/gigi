#!/usr/bin/env python3
import subprocess
import sys
import os

def check_command(cmd, label):
    print(f"[*] Checking {label}...")
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        print(f"--- {label} Output ---")
        print(res.stdout.strip() or "[No stdout]")
        if res.stderr:
            print(f"[Stderr] {res.stderr.strip()}")
        print("-" * 40)
        return True, res.stdout
    except Exception as e:
        print(f"[!] Failed to run {label}: {e}")
        print("-" * 40)
        return False, str(e)

def main():
    print("="*60)
    print("      Gigi Robot Bluetooth Telemetry Diagnostics")
    print("="*60)
    
    # 1. Check bluetooth daemon flags
    print("[*] Checking bluetoothd daemon process...")
    try:
        ps_res = subprocess.run(["ps", "aux"], stdout=subprocess.PIPE, text=True)
        bt_lines = [line for line in ps_res.stdout.splitlines() if "bluetoothd" in line]
        if bt_lines:
            for line in bt_lines:
                print(f"  {line}")
                if "-C" in line or "--compat" in line:
                    print("  -> SUCCESS: bluetoothd is running in COMPATIBILITY mode.")
                else:
                    print("  -> WARNING: bluetoothd is NOT running in compatibility mode. sdptool SP registration will fail!")
        else:
            print("  -> ERROR: bluetoothd process not found!")
    except Exception as e:
        print(f"  -> Error checking process: {e}")
    print("-" * 40)
    
    # 2. Check bluetoothctl show
    check_command(["bluetoothctl", "show"], "bluetoothctl show")
    
    # 3. Check rfcomm status
    check_command(["rfcomm", "-a"], "rfcomm -a (Active Bindings)")
    
    # 4. Check if /dev/rfcomm0 exists
    print("[*] Checking /dev/rfcomm0...")
    if os.path.exists("/dev/rfcomm0"):
        print("  -> /dev/rfcomm0 exists.")
        # Check if any process is using it (lsof or fuser)
        try:
            fuser_res = subprocess.run(["sudo", "fuser", "/dev/rfcomm0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if fuser_res.stdout.strip():
                print(f"  -> WARNING: /dev/rfcomm0 is currently locked by PID(s): {fuser_res.stdout.strip()}")
            else:
                print("  -> /dev/rfcomm0 is idle.")
        except Exception:
            pass
    else:
        print("  -> /dev/rfcomm0 does not exist.")
    print("-" * 40)
    
    # 5. Check SDP SPP registration
    print("[*] Checking registered SDP profiles (searching for Serial Port)...")
    try:
        sdp_res = subprocess.run(["sdptool", "browse", "local"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if "Serial Port" in sdp_res.stdout:
            print("  -> SUCCESS: Serial Port (SPP) profile is registered in SDP.")
        else:
            print("  -> WARNING: Serial Port (SPP) profile NOT found in SDP local registry.")
    except Exception as e:
        print(f"  -> Error running sdptool: {e}")
    print("-" * 40)

if __name__ == "__main__":
    main()
