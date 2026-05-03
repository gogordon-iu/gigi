import os
import sys
import struct
import shutil
import time

try:
    import serial
except ImportError:
    print("Error: The 'pyserial' library is required to run this script.")
    print("Please install it by running: pip install pyserial")
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        print("Usage: python bt_sender.py <path_to_activity_folder> <serial_port>")
        print("\nExamples:")
        print("  Windows: python bt_sender.py C:\\path\\to\\folder COM4")
        print("  Mac:     python bt_sender.py /path/to/folder /dev/cu.OrangePi-SerialPort")
        print("  Linux:   python bt_sender.py /path/to/folder /dev/rfcomm0")
        sys.exit(1)
        
    folder_path = os.path.abspath(sys.argv[1])
    serial_port = sys.argv[2]
    
    if not os.path.isdir(folder_path):
        print(f"Error: Directory '{folder_path}' does not exist.")
        sys.exit(1)
        
    folder_name = os.path.basename(folder_path)
    parent_dir = os.path.dirname(folder_path)
    
    # We want to zip the folder such that extracting it creates the folder itself.
    # shutil.make_archive(..., base_dir=folder_name) does exactly this.
    temp_zip = "temp_activity_sender"
    print(f"Zipping '{folder_name}'...")
    zip_path = shutil.make_archive(temp_zip, 'zip', root_dir=parent_dir, base_dir=folder_name)
    
    file_size = os.path.getsize(zip_path)
    print(f"Zip created: {zip_path} ({file_size} bytes)")
    
    print(f"Opening serial port {serial_port}...")
    try:
        ser = serial.Serial(serial_port, baudrate=115200, timeout=10)
    except Exception as e:
        print(f"Failed to open serial port {serial_port}: {e}")
        os.remove(zip_path)
        sys.exit(1)
        
    try:
        print("Waiting for receiver to sync...")
        ser.timeout = 2 # Add timeout for sync
        
        # Handshake: wait for Orange Pi to be ready
        while True:
            ser.write(b"SYNC")
            if ser.read(5) == b"READY":
                break
            time.sleep(0.5)
            
        print("Sending header...")
        ser.write(struct.pack("<Q", file_size))
        
        # Wait for header ACK
        if ser.read(3) != b"ACK":
            print("Failed to get header acknowledgment from receiver.")
            return
            
        print("Sending file data...")
        sent_bytes = 0
        CHUNK_SIZE = 4096
        with open(zip_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                ser.write(chunk)
                
                # Wait for Orange Pi to acknowledge this chunk
                # This prevents the Mac's Bluetooth buffer from overflowing and hanging!
                ack = ser.read(1)
                if ack != b"K":
                    print("\nError: Connection dropped or out of sync!")
                    break
                    
                sent_bytes += len(chunk)
                
                # Print progress
                sys.stdout.write(f"\rProgress: {sent_bytes}/{file_size} bytes ({(sent_bytes/file_size)*100:.1f}%)")
                sys.stdout.flush()
                
        print("\nFinished sending file data. Waiting a moment for receiver to process...")
        time.sleep(2) # Give it time to flush buffers over bluetooth
        
    except Exception as e:
        print(f"\nError during transfer: {e}")
    finally:
        ser.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
