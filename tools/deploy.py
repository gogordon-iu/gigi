"""
Robot deployment and synchronization utility.
Pushes the latest package code to the physical Gigi robot over SSH / pscp / rsync.
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ROBOT_IP = os.getenv("ROBOT_IP", "10.0.0.223")
ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROBOT_IP
ROBOT_USER = os.getenv("ROBOT_USER", "orangepi")
PASSWORD = os.getenv("ROBOT_PASSWORD", "orangepi")
REMOTE_PATH = os.getenv("ROBOT_REMOTE_PATH", "/home/orangepi/Code/gigi")


def run_cmd(cmd: str) -> bool:
    print(f"[Deploy] Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[Deploy] Error: {res.stderr}")
        return False
    if res.stdout:
        print(res.stdout)
    return True


def deploy():
    print(f"=== STARTING DEPLOYMENT TO GIGI ROBOT ({ROBOT_USER}@{ROBOT_IP}) ===")

    # Ensure remote directory exists
    run_cmd(f'plink -batch -pw {PASSWORD} {ROBOT_USER}@{ROBOT_IP} "mkdir -p {REMOTE_PATH}/src/gigi"')

    # Sync src package
    cmd = f'pscp -batch -pw {PASSWORD} -r src/* {ROBOT_USER}@{ROBOT_IP}:{REMOTE_PATH}/src'
    if not run_cmd(cmd):
        print("[Deploy] Failed to sync src/ directory")
        sys.exit(1)

    # Sync pyproject.toml
    run_cmd(f'pscp -batch -pw {PASSWORD} pyproject.toml {ROBOT_USER}@{ROBOT_IP}:{REMOTE_PATH}/pyproject.toml')

    print("=== DEPLOYMENT COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    deploy()
