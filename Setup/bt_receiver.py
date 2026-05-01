import os
import socket
import struct
import zipfile

PORT = 1 # RFCOMM port 1 is standard for Serial Port Profile

def main():
    # Find the Assets folder relative to this script
    # This assumes the script is in gigi/Setup/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "Assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    # Create the Bluetooth socket
    server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    server_sock.bind(("", PORT))
    server_sock.listen(1)
    
    print(f"Waiting for Bluetooth serial connection on RFCOMM channel {PORT}...")
    
    while True:
        try:
            client_sock, client_info = server_sock.accept()
            print(f"Accepted connection from {client_info}")
            
            # Read the 8-byte file size header
            header = client_sock.recv(8)
            if not header or len(header) != 8:
                print("Failed to receive valid header.")
                client_sock.close()
                continue
                
            file_size = struct.unpack("<Q", header)[0]
            print(f"Expecting file of size {file_size} bytes...")
            
            zip_path = os.path.join(base_dir, "temp_received.zip")
            received_bytes = 0
            
            with open(zip_path, "wb") as f:
                while received_bytes < file_size:
                    chunk_size = min(4096, file_size - received_bytes)
                    data = client_sock.recv(chunk_size)
                    if not data:
                        break
                    f.write(data)
                    received_bytes += len(data)
                    
            if received_bytes == file_size:
                print("File received successfully. Extracting...")
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Because we zipped the folder targeting the folder itself from the sender,
                    # extracting it to Assets/ will correctly yield Assets/FolderName/...
                    zip_ref.extractall(assets_dir)
                print(f"Successfully extracted to {assets_dir}")
            else:
                print(f"Incomplete file transfer. Got {received_bytes}/{file_size} bytes.")
                
        except Exception as e:
            print(f"Error during transfer: {e}")
        finally:
            if 'client_sock' in locals():
                client_sock.close()
            if 'zip_path' in locals() and os.path.exists(zip_path):
                os.remove(zip_path)
        print("\nWaiting for next connection...")

if __name__ == "__main__":
    main()
