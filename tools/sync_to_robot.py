import os
import subprocess
import time
from pathlib import Path

ROBOT_IP = "10.0.0.223"
ROBOT_USER = "orangepi"
ROBOT_PASSWORD = "orangepi"
REMOTE_BASE = "/home/orangepi/Code/gigi"
LOCAL_ROOT = Path(__file__).resolve().parent.parent

def run_remote(cmd: str):
    full_cmd = f'plink -batch -pw {ROBOT_PASSWORD} {ROBOT_USER}@{ROBOT_IP} "{cmd}"'
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout, res.stderr

def copy_file(local_path: Path, remote_path: str):
    cmd = f'pscp -batch -pw {ROBOT_PASSWORD} "{local_path}" {ROBOT_USER}@{ROBOT_IP}:{remote_path}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"Copy {local_path.name} -> {remote_path}: {'OK' if res.returncode == 0 else 'FAILED'}")
    return res.returncode == 0

def copy_dir(local_dir: Path, remote_dir: str):
    # Ensure remote directory exists
    run_remote(f"mkdir -p '{remote_dir}'")
    cmd = f'pscp -batch -pw {ROBOT_PASSWORD} -r "{local_dir}"/* {ROBOT_USER}@{ROBOT_IP}:"{remote_dir}"/'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"Copy dir {local_dir.name} -> {remote_dir}: {'OK' if res.returncode == 0 else 'FAILED'}")
    return res.returncode == 0

def main():
    print(f"[*] Syncing updated modules to physical robot ({ROBOT_IP})...")

    # 1. Update Python source files
    copy_file(LOCAL_ROOT / "src" / "gigi" / "core" / "daemon.py", f"{REMOTE_BASE}/src/gigi/core/daemon.py")
    copy_file(LOCAL_ROOT / "src" / "gigi" / "activities" / "alive_mode" / "alive_mode.py", f"{REMOTE_BASE}/src/gigi/activities/alive_mode/alive_mode.py")
    copy_file(LOCAL_ROOT / "src" / "gigi" / "activities" / "social" / "face_recognition_demo.py", f"{REMOTE_BASE}/src/gigi/activities/social/face_recognition_demo.py")
    copy_file(LOCAL_ROOT / "src" / "gigi" / "expression" / "face_display.py", f"{REMOTE_BASE}/src/gigi/expression/face_display.py")
    copy_file(LOCAL_ROOT / "Setup" / "start_bluetooth_hub.sh", f"{REMOTE_BASE}/Setup/start_bluetooth_hub.sh")

    # 2. Sync restored and custom activity plans into Assets
    assets_to_sync = [
        "activity_plan_mars_habitat",
        "activity_plan_waves_energy",
        "activity_plan_ai_ethics",
        "activity_plan_storytelling",
        "custom_interaction_greeter",
        "custom_interaction_guessing_game",
    ]
    for asset in assets_to_sync:
        local_asset_dir = LOCAL_ROOT / "Assets" / asset
        if local_asset_dir.exists():
            remote_asset_dir = f"{REMOTE_BASE}/Assets/{asset}"
            copy_dir(local_asset_dir, remote_asset_dir)

    # 3. Ensure permissions and X11 access for root
    print("[*] Updating X11 authorization and script permissions on robot...")
    run_remote("echo orangepi | sudo -S cp -f /home/orangepi/.Xauthority /root/.Xauthority")
    run_remote(f"chmod +x {REMOTE_BASE}/Setup/start_bluetooth_hub.sh")

    # 4. Restart gigi-bluetooth.service
    print("[*] Restarting gigi-bluetooth.service on robot...")
    code, out, err = run_remote("echo orangepi | sudo -S systemctl restart gigi-bluetooth.service")
    print(f"Restart service: {'OK' if code == 0 else 'FAILED'} {err.strip()}")

    time.sleep(3)
    code, out, err = run_remote("echo orangepi | sudo -S systemctl is-active gigi-bluetooth.service")
    print(f"Service status: {out.strip()}")

    # 5. Verify daemon scans activities
    print("[*] Verifying daemon activity scan on robot...")
    test_cmd = (
        f"cd {REMOTE_BASE} && {REMOTE_BASE}/.venv/bin/python -c \""
        "import sys; sys.path.insert(0, 'src'); "
        "from gigi.core.daemon import scan_activity_plans, scan_custom_interactions, scan_files; "
        "p=scan_activity_plans(); i=scan_custom_interactions(); d,_,_=scan_files(); "
        "filenames = set(x['filename'] for x in d.values()); "
        "print('ROBOT READY:', len(filenames), 'core,', len(p), 'plans,', len(i), 'custom')"
        "\""
    )
    code, out, err = run_remote(test_cmd)
    print(f"Robot scan result: {out.strip()}")

if __name__ == "__main__":
    main()
