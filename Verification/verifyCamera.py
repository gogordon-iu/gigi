import cv2
from pyzbar.pyzbar import decode

def find_camera_ports():
    """
    Detect available camera ports.
    """
    available_ports = []
    for port in range(10):  # Try ports 0-9
        print("Checking port ", port)
        cap = cv2.VideoCapture(port)
        if cap.isOpened():
            available_ports.append(port)
            cap.release()
            break
    return available_ports

def scan_qr_code(camera_port):
    """
    Start scanning QR codes from the specified camera port.
    """
    cap = cv2.VideoCapture(camera_port)
    if not cap.isOpened():
        print(f"Unable to open camera at port {camera_port}")
        return

    print("Waiting for QR code...")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame. Exiting.")
                break

            decoded_objects = decode(frame)
            if decoded_objects:
                for obj in decoded_objects:
                    qr_data = obj.data.decode('utf-8')
                    print(f"QR Code detected: {qr_data}")
                    cap.release()
                    cv2.destroyAllWindows()
                    return
            
            # Display the frame (optional)
            cv2.imshow('QR Code Scanner', frame)
            
            # Exit with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Exiting...")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Step 1: Find available camera ports
    print("Scanning for available camera ports...")
    ports = find_camera_ports()
    if not ports:
        print("No camera ports detected. Please connect a camera.")
    else:
        print(f"Available camera ports: {ports}")
        # Step 2: Select the first available camera port
        selected_port = ports[0]
        print(f"Using camera at port {selected_port}")
        # Step 3: Start scanning for QR codes
        scan_qr_code(selected_port)
