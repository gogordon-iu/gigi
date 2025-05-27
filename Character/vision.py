import cv2
from pyzbar.pyzbar import decode
import threading
import sys
from datetime import datetime
from time import sleep, time

class Vision:
    def __init__(self, verbose=False):
        print("Initializing vision ...")
        self.verbose = verbose
        self.cap = self.open_camera()
        self.found = {
            "qr": {},
            "face": {}
        }
        # Load the Haar cascade for face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        self.thread = None
        self.stop_event = None

   
    def open_camera(self):
        for port in range(10):  # Try ports 0-9
            print("Checking port ", port)
            cap = cv2.VideoCapture(port)
            if cap.isOpened():
                return cap
        print(f"Unable to open camera!")
        return None
    
    def look_for(self, what=None):
        if what is None:
            what = self.found.keys()
        debug = 0
        while not self.stop_event.is_set():
            debug += 1

            ret, frame = self.cap.read()
            if not ret:
                print("Failed to capture frame. Exiting.")
                self.stop_event.set()
                return
            height, width = frame.shape[:2]

            if "qr" in what:
                decoded_objects = decode(frame)
                if decoded_objects:
                    for obj in decoded_objects:
                        qr_data = obj.data.decode('utf-8')
                        self.found["qr"][qr_data] = {
                            "box": obj.rect,
                            "center": (obj.rect.left + obj.rect.width // 2, obj.rect.top + obj.rect.height // 2),
                            "offset": (((width // 2) - (obj.rect.left + obj.rect.width // 2)) / width, ((height // 2) - (obj.rect.top + obj.rect.height // 2)) / height)
                        }
                    if self.verbose:
                        print(f"QR Code detected: {qr_data}")
                        # stop_event.set()  # DEBUG
                        # return    # DEBUG

            if "face" in what:
                gray_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Detect faces
                faces = self.face_cascade.detectMultiScale(gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                for iface, (x, y, w, h) in enumerate(faces):
                    self.found["face"][iface] = {
                        "box": (x, y, w, h),
                        "center": ((x + w // 2), (y + h // 2)),
                        "offset": (((width // 2) - (x + w // 2)) / width, ((height // 2) - (y + h // 2)) / height)
                    }
                if len(self.found["face"]) > 0:
                    if self.verbose:
                        print(self.found["face"])
                        filename = datetime.now().strftime("face_%Y-%m-%d_%H-%M-%S.jpg")
                        cv2.imwrite(filename, frame)
                        for (x, y, w, h) in faces:
                            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        filename = datetime.now().strftime("detected_face_%Y-%m-%d_%H-%M-%S.jpg")
                        cv2.imwrite(filename, frame)
                    # stop_event.set()  # DEBUG
                    # return # DEBUG
                else:
                    if self.verbose:
                        print("Face not detected...")
            # if debug > 1000:
            #     return

    def vision_thread(self, what=None, stop_event=None):
        if stop_event is None:
            self.stop_event = threading.Event()
        else:
            self.stop_event = stop_event
        t = threading.Thread(target=self.look_for, args=[what])
        return t

    def run_vision(self, what=None):
        if not self.thread:
            self.thread = self.vision_thread(what=what)
            self.thread.start()
            sleep(2)

    def stop_vision(self):
        if self.stop_event:            
            self.stop_event.set()
            if self.thread:
                self.thread.join()
                self.thread = None

    def look_and_stop(self, what=None, timeout=-1):
        self.found[what] = {}

        self.run_vision(what=what)
        if timeout < 0:
            timeout = 2

        start_time = time()
        remaining_timeout = timeout
        while remaining_timeout > 0 and len(self.found[what]) == 0:
            sleep(0.1)
            remaining_timeout = timeout - (time() - start_time)
        if len(self.found[what]) > 0:
            self.stop_vision()
        if self.verbose:
            print(f"Found {what}: {self.found[what]}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        what = sys.argv[1]
    else:
        what = "face"
    vision = Vision(verbose=True)
    vision.look_and_stop(what=what, timeout=10)
    # vision.run_vision(what=what)
    # sleep(30)
    # vision.stop_vision()