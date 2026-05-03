import os
import sys
import struct
import zipfile
import time

try:
    import serial
except ImportError:
    print("Error: The 'pyserial' library is required. Please run: pip install pyserial")
    sys.exit(1)

import subprocess

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "Assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    port_name = "/dev/rfcomm0"
    
    print("="*60)
    print(" Bluetooth Receiver (Virtual Environment Mode)")
    print("="*60)
    print(f"Starting background Bluetooth bridge...")
    
    # Kill any existing stray rfcomm processes on this port
    subprocess.run(["sudo", "pkill", "-f", f"rfcomm watch {port_name}"], stderr=subprocess.DEVNULL)
    
    # Start rfcomm watch (may prompt for sudo password)
    rfcomm_proc = subprocess.Popen(["sudo", "rfcomm", "watch", port_name, "1"])
    
    print("="*60)
    print("\nWaiting for sender to connect...")
    
    try:
        while True:
            try:
                # This blocks/fails until the Windows sender actually connects 
                # and the `rfcomm watch` command creates the /dev/rfcomm0 device.
                with serial.Serial(port_name, baudrate=115200, timeout=10) as ser:
                    print("\n>>> Connection established! Waiting for SYNC...")
                    
                    # Wait for sender to say SYNC
                    sync_data = ser.read(4)
                    if sync_data != b"SYNC":
                        continue
                        
                    # Tell sender we are ready
                    ser.write(b"READY")
                    
                    header = ser.read(8)
                    if not header or len(header) != 8:
                        print("Failed to receive valid header.")
                        continue

                    file_size = struct.unpack("<Q", header)[0]
                    print(f"Expecting file of size {file_size} bytes...")
                    
                    # Tell sender we got the header
                    ser.write(b"ACK")
                    
                    zip_path = os.path.join(base_dir, "temp_received.zip")
                    received_bytes = 0
                    CHUNK_SIZE = 4096
                
                    with open(zip_path, "wb") as f:
                        while received_bytes < file_size:
                            chunk_size = min(CHUNK_SIZE, file_size - received_bytes)
                            
                            # Read exact chunk size to ensure alignment
                            data = b""
                            while len(data) < chunk_size:
                                packet = ser.read(chunk_size - len(data))
                                if not packet:
                                    break
                                data += packet
                                
                            if len(data) < chunk_size:
                                break
                                
                            f.write(data)
                            received_bytes += len(data)
                            
                            # Acknowledge this chunk so sender can send the next one
                            ser.write(b"K")
                        
                    if received_bytes == file_size:
                        print("File received successfully. Extracting...")
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(assets_dir)
                        print(f"Successfully extracted to {assets_dir}")
                    else:
                        print(f"Incomplete transfer. Got {received_bytes}/{file_size} bytes.")
                    
            except serial.SerialException:
                # Port doesn't exist yet, which means no one has connected. Just wait and poll.
                time.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(2)
            finally:
                if 'zip_path' in locals() and os.path.exists(zip_path):
                    os.remove(zip_path)
                        
    except KeyboardInterrupt:
        print("\nExiting...")
        
    finally:
        print("Stopping Bluetooth bridge...")
        if 'rfcomm_proc' in locals():
            rfcomm_proc.terminate()
        subprocess.run(["sudo", "pkill", "-f", f"rfcomm watch {port_name}"], stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    main()
