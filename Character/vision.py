import cv2
from pyzbar.pyzbar import decode
import threading
import sys
from datetime import datetime
from time import sleep, time

class Vision:
    def __init__(self, port=None, verbose=False):
        print("Initializing vision ...")
        self.verbose = verbose
        self.cap = self.open_camera(port)
        self.found = {
            "qr": {},
            "face": {},
            "motion": {}
        }
        # Load the Haar cascade for face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        self.thread = None
        self.stop_event = None

        self.finding_motion = False

   
    def open_camera(self, port):
        if port is None:
            ports = range(10)
        else:
            ports = [port]
        for port in ports:  # Try ports 0-9
            print("Checking port ", port)
            cap = cv2.VideoCapture(port)
            if cap.isOpened():
                return cap
        print(f"Unable to open camera!")
        return None
    

    def detect_qr(self, frame):
        height, width = frame.shape[:2]
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

    def detect_motion(self, frame):
        # parameters
        blur_k = 21
        alpha = 0.02
        thr = 25
        min_area = 1000

        # resize to reasonable width for speed (maintain aspect ratio)
        max_width = 800
        height, width = frame.shape[:2]
        scale = 1.0
        if width > max_width:
            scale = max_width / float(width)

        def resize_frame(f):
            if scale != 1.0:
                return cv2.resize(f, (int(f.shape[1]*scale), int(f.shape[0]*scale)))
            return f

        if not self.finding_motion:
            self.finding_motion = True
            frame = resize_frame(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0).astype("float32")

            self.background = gray.copy()  # float32 background model

        frame = resize_frame(frame)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_blur = cv2.GaussianBlur(frame_gray, (blur_k, blur_k), 0)

        # Update running average background (float32)
        cv2.accumulateWeighted(frame_blur.astype("float32"), self.background, alpha)

        # Compute absolute difference between background and current frame
        background_uint8 = cv2.convertScaleAbs(self.background)  # convert to uint8 for absdiff
        diff = cv2.absdiff(background_uint8, frame_blur)

        # Threshold to get motion regions
        _, motion_mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

        # Morphological ops to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        motion_mask = cv2.dilate(motion_mask, kernel, iterations=2)

        # Find contours on mask
        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            self.found['motion'][i] = {
                        "box": (x, y, w, h),
                        "center": ((x + w // 2), (y + h // 2)),
                        "offset": (((width // 2) - (x + w // 2)) / width, ((height // 2) - (y + h // 2)) / height)
                    }

    def look_for(self, what=None):
        print(f"Looking for {what} ...")
        if what is None:
            what = self.found.keys()
        debug = 0
        print(f"Looking for {what} ...")
        while not self.stop_event.is_set():
            debug += 1

            ret, frame = self.cap.read()
            if not ret:
                print("Failed to capture frame. Exiting.")
                self.stop_event.set()
                return
            height, width = frame.shape[:2]

            if "qr" in what:
                self.detect_qr(frame)

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

            if "motion" in what:
                self.detect_motion(frame)

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