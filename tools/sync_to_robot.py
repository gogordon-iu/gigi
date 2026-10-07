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
    # Try native OpenSSH first
    full_cmd = f'ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new {ROBOT_USER}@{ROBOT_IP} "{cmd}"'
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        # Fallback to plink if SSH key not configured
        full_cmd = f'plink -batch -pw {ROBOT_PASSWORD} {ROBOT_USER}@{ROBOT_IP} "{cmd}"'
        res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode, res.stdout, res.stderr

def copy_file(local_path: Path, remote_path: str):
    cmd = f'scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new "{local_path}" {ROBOT_USER}@{ROBOT_IP}:{remote_path}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        cmd = f'pscp -batch -pw {ROBOT_PASSWORD} "{local_path}" {ROBOT_USER}@{ROBOT_IP}:{remote_path}'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"Copy {local_path.name} -> {remote_path}: {'OK' if res.returncode == 0 else 'FAILED'}")
    return res.returncode == 0

def copy_dir(local_dir: Path, remote_dir: str):
    # Ensure remote parent directory exists
    remote_dir_norm = remote_dir.replace("\\", "/").rstrip("/")
    parent_remote = os.path.dirname(remote_dir_norm)
    run_remote(f"mkdir -p '{parent_remote}'")
    cmd = f'scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new -r "{local_dir}" {ROBOT_USER}@{ROBOT_IP}:"{parent_remote}/"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        cmd = f'pscp -batch -pw {ROBOT_PASSWORD} -r "{local_dir}" {ROBOT_USER}@{ROBOT_IP}:"{parent_remote}/"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"Copy dir {local_dir.name} -> {remote_dir}: {'OK' if res.returncode == 0 else 'FAILED'}")
    return res.returncode == 0

def main():
    print(f"[*] Syncing updated modules to physical robot ({ROBOT_IP})...")

    # 1. Sync full Python source tree and setup scripts
    print("[*] Syncing src/ package tree...")
    copy_dir(LOCAL_ROOT / "src", f"{REMOTE_BASE}/src")

    print("[*] Syncing Setup/ directory...")
    copy_dir(LOCAL_ROOT / "Setup", f"{REMOTE_BASE}/Setup")

    print("[*] Syncing docs/ and project configs...")
    if (LOCAL_ROOT / "docs").exists():
        copy_dir(LOCAL_ROOT / "docs", f"{REMOTE_BASE}/docs")
    copy_file(LOCAL_ROOT / "pyproject.toml", f"{REMOTE_BASE}/pyproject.toml")
    copy_file(LOCAL_ROOT / "BUG_LOG.md", f"{REMOTE_BASE}/BUG_LOG.md")

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
    run_remote(f"chmod +x {REMOTE_BASE}/Setup/*.sh {REMOTE_BASE}/Setup/*.py")

    # 4. Restart gigi-bluetooth.service
    print("[*] Restarting gigi-bluetooth.service on robot...")
    code, out, err = run_remote("echo orangepi | sudo -S systemctl restart gigi-bluetooth.service")
    print(f"Restart service: {'OK' if code == 0 else 'FAILED'} {err.strip()}")

    time.sleep(3)
    code, out, err = run_remote("echo orangepi | sudo -S systemctl is-active gigi-bluetooth.service")
    print(f"Service status: {out.strip()}")

    # 5. Verify daemon scans activities
    print("[*] Verifying daemon activity scan on robot...")
    import base64
    scan_script = (
        "import sys; sys.path.insert(0, 'src'); "
        "from gigi.core.daemon import scan_activity_plans, scan_custom_interactions, scan_files; "
        "p=scan_activity_plans(); i=scan_custom_interactions(); d,_,_=scan_files(); "
        "print('ROBOT READY:', len(d), 'core,', len(p), 'plans,', len(i), 'custom')"
    )
    b64_code = base64.b64encode(scan_script.encode()).decode()
    test_cmd = f"cd {REMOTE_BASE} && echo {b64_code} | base64 -d | {REMOTE_BASE}/.venv/bin/python"
    code, out, err = run_remote(test_cmd)
    for line in out.splitlines():
        if "ROBOT READY" in line:
            print(f"Robot scan result: {line.strip()}")

if __name__ == "__main__":
    main()
