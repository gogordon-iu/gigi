import subprocess
import sys
import os

ROBOT_IP = "10.0.0.223"
PASSWORD = "orangepi"
REMOTE_PATH = "/home/orangepi/Code/gigi"

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error executing command: {res.stderr}")
        return False
    if res.stdout:
        print(res.stdout)
    return True

def main():
    print("=== STARTING PUSH TO ROBOT ===")
    
    # 1. Sync source folders
    folders = ["Character", "Demo", "Zhennan", "Assets/activity_plan_waves_energy"]
    for folder in folders:
        # Ensure remote directory exists
        mkdir_cmd = f'plink -pw {PASSWORD} orangepi@{ROBOT_IP} "mkdir -p {REMOTE_PATH}/{folder}"'
        run_cmd(mkdir_cmd)
        # Use pscp with recursive flag
        cmd = f'pscp -pw {PASSWORD} -r {folder}/* orangepi@{ROBOT_IP}:{REMOTE_PATH}/{folder}'
        if not run_cmd(cmd):
            print(f"Failed to sync folder: {folder}")
            sys.exit(1)
            
    # 2. Sync test_vision_listening.py
    cmd = f'pscp -pw {PASSWORD} test_vision_listening.py orangepi@{ROBOT_IP}:{REMOTE_PATH}/test_vision_listening.py'
    if not run_cmd(cmd):
        print("Failed to sync test_vision_listening.py")
        sys.exit(1)
        
    # 3. Always copy motorData_calibrated_local.json to motorData_calibrated.json on the robot
    print("Enforcing robot-specific motor calibration (copying local file to standard calibrated file)...")
    cmd = f'plink -pw {PASSWORD} orangepi@{ROBOT_IP} "cp {REMOTE_PATH}/Character/motorData_calibrated_local.json {REMOTE_PATH}/Character/motorData_calibrated.json"'
    if not run_cmd(cmd):
        print("Failed to restore robot-specific motor calibration on the robot!")
        sys.exit(1)
        
    print("=== PUSH COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
