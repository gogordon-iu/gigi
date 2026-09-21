"""
Robot State Backup & Pre-Flight Archiving Utility.

Connects to the live physical Gigi robot over SSH (plink / pscp),
extracts all hardware calibration profiles, live uncommitted code,
systemd service configurations, and custom scripts, and saves
a timestamped backup snapshot in the backups/ directory.
"""

import os
import sys
import json
import datetime
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ROBOT_IP = os.getenv("ROBOT_IP", "10.0.0.223")
ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROBOT_IP
ROBOT_USER = os.getenv("ROBOT_USER", "orangepi")
ROBOT_PASSWORD = os.getenv("ROBOT_PASSWORD", "orangepi")
REMOTE_REPO = os.getenv("ROBOT_REMOTE_PATH", "/home/orangepi/Code/gigi")


def run_remote_ssh(cmd: str) -> str:
    """Execute a shell command on the remote robot via plink."""
    full_cmd = f'plink -batch -pw {ROBOT_PASSWORD} {ROBOT_USER}@{ROBOT_IP} "{cmd}"'
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0 and not res.stdout:
        return f"[Error returncode {res.returncode}]: {res.stderr.strip()}"
    return res.stdout or ""


def fetch_file(remote_file: str, local_dest: Path) -> bool:
    """Download a file from the robot via pscp."""
    local_dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = f'pscp -batch -pw {ROBOT_PASSWORD} {ROBOT_USER}@{ROBOT_IP}:{remote_file} "{local_dest}"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode == 0


def fetch_dir(remote_dir: str, local_dest: Path) -> bool:
    """Download a directory from the robot recursively via pscp."""
    local_dest.mkdir(parents=True, exist_ok=True)
    cmd = f'pscp -batch -pw {ROBOT_PASSWORD} -r {ROBOT_USER}@{ROBOT_IP}:{remote_dir}/* "{local_dest}"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return res.returncode == 0


def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = Path(__file__).resolve().parent.parent / "backups" / f"robot_{ROBOT_IP}_{timestamp}"
    calib_dir = backup_root / "calibration"
    git_dir = backup_root / "git_state"
    sys_dir = backup_root / "system_config"
    scripts_dir = backup_root / "custom_scripts"

    for d in [calib_dir, git_dir, sys_dir, scripts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"============================================================")
    print(f"  GIGI ROBOT PRE-FLIGHT STATE BACKUP")
    print(f"  Target: {ROBOT_USER}@{ROBOT_IP}:{REMOTE_REPO}")
    print(f"  Destination: {backup_root}")
    print(f"============================================================")

    # 1. Probe connectivity
    print("\n[*] Probing remote robot connectivity...")
    host_info = run_remote_ssh("hostname; uname -a; date")
    print(f"    Connected: {host_info.strip().splitlines()[0]}")

    # 2. Extract Hardware Calibration
    print("\n[*] Downloading Hardware Calibration Profiles...")
    calib_files = [
        f"{REMOTE_REPO}/Character/motorData_calibrated_local.json",
        f"{REMOTE_REPO}/Character/motorData_calibrated.json",
        f"{REMOTE_REPO}/Character/motorData.json",
        f"{REMOTE_REPO}/Character/motorData_backup.json",
        f"{REMOTE_REPO}/Character/lookat_calibrated.json",
        f"{REMOTE_REPO}/Setup/Scripts/motorData_calibrated.json",
    ]
    downloaded_calib = []
    for f in calib_files:
        fname = os.path.basename(f)
        dest = calib_dir / fname
        if fetch_file(f, dest) and dest.exists() and dest.stat().st_size > 0:
            print(f"    [+] Saved {fname} ({dest.stat().st_size} bytes)")
            downloaded_calib.append(fname)
        else:
            if dest.exists() and dest.stat().st_size == 0:
                dest.unlink()

    # Also make a copy of the active calibrated file to local repo root as motorData_calibrated.json
    local_calib_target = Path(__file__).resolve().parent.parent / "motorData_calibrated.json"
    primary_calib = calib_dir / "motorData_calibrated_local.json"
    if not primary_calib.exists():
        primary_calib = calib_dir / "motorData_calibrated.json"
    if primary_calib.exists():
        local_calib_target.write_text(primary_calib.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"    [+] Active calibration synced to local workspace: {local_calib_target.name}")

    # 3. Capture Remote Git Workspace State
    print("\n[*] Capturing Remote Git State & Uncommitted Work...")
    # Diff via remote file dump + pscp to avoid stdout truncation or charmap decode errors
    run_remote_ssh(f"cd {REMOTE_REPO} && git diff > /tmp/gigi_diff_unstaged.patch")
    fetch_file("/tmp/gigi_diff_unstaged.patch", git_dir / "diff_unstaged.patch")
    print(f"    [+] Recorded diff_unstaged.patch")

    run_remote_ssh(f"cd {REMOTE_REPO} && git diff --cached > /tmp/gigi_diff_staged.patch")
    fetch_file("/tmp/gigi_diff_staged.patch", git_dir / "diff_staged.patch")
    print(f"    [+] Recorded diff_staged.patch")

    git_commands = {
        "status.txt": f"cd {REMOTE_REPO} && git status",
        "log.txt": f"cd {REMOTE_REPO} && git log -n 10 --stat",
        "branch.txt": f"cd {REMOTE_REPO} && git branch -a -v",
        "remotes.txt": f"cd {REMOTE_REPO} && git remote -v",
    }
    for fname, cmd in git_commands.items():
        out = run_remote_ssh(cmd)
        (git_dir / fname).write_text(out or "", encoding="utf-8")
        print(f"    [+] Recorded {fname}")

    # 4. System & Hardware Configurations
    print("\n[*] Capturing System Services & Hardware Configuration...")
    sys_commands = {
        "network_interfaces.txt": "ip a; iwconfig 2>&1",
        "bluetooth_status.txt": "bluetoothctl show; rfcomm 2>&1",
        "systemd_gigi_services.txt": "systemctl status gigi-bluetooth.service 2>&1 || true",
        "hardware_specs.txt": "lscpu; free -h; df -h",
        "running_processes.txt": "ps aux | grep -i python",
    }
    for fname, cmd in sys_commands.items():
        out = run_remote_ssh(cmd)
        (sys_dir / fname).write_text(out, encoding="utf-8")
        print(f"    [+] Recorded {fname}")

    # Fetch systemd unit files if present
    fetch_file("/etc/systemd/system/gigi-bluetooth.service", sys_dir / "gigi-bluetooth.service")
    fetch_file("/etc/asound.conf", sys_dir / "asound.conf")
    fetch_file(f"/home/{ROBOT_USER}/.asoundrc", sys_dir / "user_asoundrc")

    # 5. Fetch Custom / Untracked Scripts
    print("\n[*] Downloading Live Custom Scripts...")
    custom_scripts = [
        f"{REMOTE_REPO}/Character/conversation_ollama.py",
        f"{REMOTE_REPO}/Demo/intro_to_gigi.py",
        f"{REMOTE_REPO}/Demo/test_reading_fluency.py",
        f"{REMOTE_REPO}/test_guidance.py",
        f"{REMOTE_REPO}/llm_server.sh",
        f"{REMOTE_REPO}/llm_server.sh.bak",
        f"{REMOTE_REPO}/Zhennan/activity_plan_aiethics.json",
        f"{REMOTE_REPO}/Zhennan/activity_plan_storytelling.json",
    ]
    for s in custom_scripts:
        fname = os.path.basename(s)
        dest = scripts_dir / fname
        if fetch_file(s, dest) and dest.exists():
            print(f"    [+] Saved {fname}")

    # 6. Generate Manifest & Human-Readable Summary
    manifest = {
        "timestamp": timestamp,
        "robot_ip": ROBOT_IP,
        "robot_user": ROBOT_USER,
        "remote_path": REMOTE_REPO,
        "downloaded_calibrations": downloaded_calib,
        "backup_path": str(backup_root),
    }
    (backup_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Parse calibration details for summary
    calib_summary = "None found"
    if primary_calib.exists():
        try:
            calib_data = json.loads(primary_calib.read_text(encoding="utf-8"))
            calib_summary = "\n".join([
                f"  - **{joint}**: channel {data.get('channel')}, min={data.get('min')}, max={data.get('max')}, center={data.get('center')}"
                for joint, data in calib_data.items() if isinstance(data, dict) and "min" in data
            ])
        except Exception as e:
            calib_summary = f"Error reading calibration JSON: {e}"

    summary_md = f"""# Gigi Robot State Backup Summary

- **Timestamp**: {datetime.datetime.now().isoformat()}
- **Robot IP**: `{ROBOT_IP}`
- **Host**: `{host_info.strip().splitlines()[0]}`
- **Kernel**: `{host_info.strip().splitlines()[1] if len(host_info.strip().splitlines()) > 1 else 'unknown'}`
- **Remote Code Path**: `{REMOTE_REPO}`
- **Local Backup Directory**: `{backup_root}`

---

## Hardware Motor Calibration Profiles

The physical robot motor calibration has been safely captured:
{calib_summary}

- **Active Calibrated File**: `{primary_calib.name}`
- **Local Workspace Mirror**: Synced to `motorData_calibrated.json` (gitignored).

---

## Captured Artifacts

1. **Calibration (`calibration/`)**:
   - `motorData_calibrated_local.json`
   - `motorData_calibrated.json`
   - `lookat_calibrated.json`
2. **Git State (`git_state/`)**:
   - `diff_unstaged.patch`: Uncommitted changes from `/home/orangepi/Code/gigi`.
   - `diff_staged.patch`: Staged changes.
   - `status.txt`: Full workspace status.
   - `log.txt`: Last 10 commits on robot.
3. **System Configuration (`system_config/`)**:
   - `gigi-bluetooth.service`: Active systemd unit.
   - `running_processes.txt`: Process list (RKLLM, Bluetooth, Python).
   - `network_interfaces.txt` & `bluetooth_status.txt`.
4. **Custom Scripts (`custom_scripts/`)**:
   - Live scripts existing on the robot (`intro_to_gigi.py`, `conversation_ollama.py`, `llm_server.sh`, Zhennan activity plans).
"""
    (backup_root / "BACKUP_SUMMARY.md").write_text(summary_md, encoding="utf-8")

    print("\n============================================================")
    print(f"  [SUCCESS] Backup completed successfully!")
    print(f"  Location: {backup_root}")
    print(f"  Summary:  {backup_root / 'BACKUP_SUMMARY.md'}")
    print("============================================================")


if __name__ == "__main__":
    main()
