import subprocess
import sys
import os

DEFAULT_ROBOT_IP = "10.0.0.223"
ROBOT_IP = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ROBOT_IP", DEFAULT_ROBOT_IP)
PASSWORD = "orangepi"
REMOTE_PATH = "/home/orangepi/Code/gigi"

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error executing command: {res.stderr}")
        return False
    print(res.stdout)
    return True

def deploy():
    print(f"=== STARTING DEPLOYMENT TO ROBOT ({ROBOT_IP}) ===")
    
    # 1. Sync main code folders
    folders = ["Character", "Demo", "Zhennan"]
    for folder in folders:
        # Use pscp with recursive flag
        cmd = f'pscp -batch -pw {PASSWORD} -r {folder}/* orangepi@{ROBOT_IP}:{REMOTE_PATH}/{folder}'
        if not run_cmd(cmd):
            print(f"Deployment failed at folder: {folder}")
            sys.exit(1)
            
    # 2. Sync test_vision_listening.py
    cmd = f'pscp -batch -pw {PASSWORD} test_vision_listening.py orangepi@{ROBOT_IP}:{REMOTE_PATH}/test_vision_listening.py'
    if not run_cmd(cmd):
        print("Deployment failed at test_vision_listening.py")
        sys.exit(1)
        
    # 3. Always copy motorData_calibrated_local.json to motorData_calibrated.json on the robot
    print("Copying calibrated motor JSON file on the robot...")
    cmd = f'plink -batch -pw {PASSWORD} orangepi@{ROBOT_IP} "cp {REMOTE_PATH}/Character/motorData_calibrated_local.json {REMOTE_PATH}/Character/motorData_calibrated.json"'
    if not run_cmd(cmd):
        print("Failed to copy calibrated motor JSON file on the robot!")
        sys.exit(1)
        
    print("=== DEPLOYMENT COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    deploy()
