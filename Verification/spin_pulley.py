# When detect motion, move motor

from datetime import datetime
import cv2
from verifyDCMotor import *

class SpinPulley:
    def __init__(self):
        self.motion_detection_stage = "inactive"
        self.motion_detection_calibration = 0
        self.motion_detection_duration = 30  # number of frames to calibrate background
        self.background = None
        self.save_motion_frames = False

        self.cap = self.open_camera(port=None)

        self.motion_detected = False

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
    
    def detect_motion(self, frame):
        height, width = frame.shape[:2]

        # parameters
        blur_k = 21
        alpha = 0.02
        thr = 120
        min_area = 1000

        # resize to reasonable width for speed (maintain aspect ratio)
        max_width = 800
        
        scale = 1.0
        if width > max_width:
            scale = max_width / float(width)

        def resize_frame(f):
            if scale != 1.0:
                return cv2.resize(f, (int(f.shape[1]*scale), int(f.shape[0]*scale)))
            return f

        if self.motion_detection_stage == "inactive":
            self.motion_detection_stage = "acquire_background"
            frame = resize_frame(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0).astype("float32")

            self.background = gray.copy()  # float32 background model

        height, width = frame.shape[:2]
        max_area = height * width / 4

        frame = resize_frame(frame)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_blur = cv2.GaussianBlur(frame_gray, (blur_k, blur_k), 0)

        # Update running average background (float32)
        cv2.accumulateWeighted(frame_blur.astype("float32"), self.background, alpha)

        if self.motion_detection_stage == "acquire_background":
            self.motion_detection_calibration += 1
            if self.motion_detection_calibration > self.motion_detection_duration:
                self.motion_detection_stage = "active"
                self.motion_detection_calibration = 0

        print(f"Stage {self.motion_detection_stage}, Calibration {self.motion_detection_calibration}")

        if self.motion_detection_stage == "active":

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

            motion_boxes = []
            for i, cnt in enumerate(contours):
                area = cv2.contourArea(cnt)
                if area < min_area or area > max_area:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                if self.save_motion_frames:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 180, 255), 2)
                motion_boxes.append({
                            "box": (x, y, w, h),
                            "center": ((x + w // 2), (y + h // 2)),
                            "offset": (((width // 2) - (x + w // 2)) / width, ((height // 2) - (y + h // 2)) / height)
                            })
            if self.save_motion_frames and len(motion_boxes) > 0:
                text = f"Motion boxes: {len(motion_boxes)} Stage {self.motion_detection_stage}"
                cv2.putText(frame, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)
                filename = datetime.now().strftime("motion_%Y-%m-%d_%H-%M-%S.jpg")
                cv2.imwrite(filename, frame)

            # Motion Detected!
            if len(motion_boxes) > 0:
                self.motion_detected = True
                try:
                    self.move_motor_on_motion()
                except Exception as e:
                    print(f"Error occurred while moving motor: {e}")
                self.motion_detection_stage = "inactive"    # reset the motion detection
        return self.motion_detected

    def move_motor_on_motion(self):
        # Example motor movement on motion detection
        print("Motion detected! Spinning pulley motor.")
        forward(2)  # Spin forward for 2 seconds
        time.sleep(1)
        reverse(2)  # Spin reverse for 2 seconds
        stop()

if __name__ == "__main__":
    spinner = SpinPulley()
    if spinner.cap is None:
        print("No camera available, exiting.")
        exit(1)

    while True:
        ret, frame = spinner.cap.read()
        if not ret:
            print("Failed to read frame from camera, exiting.")
            break

        motion_detected = spinner.detect_motion(frame)
        if motion_detected:
            print("Action taken on motion detection.")
            break

    spinner.cap.release()
    cv2.destroyAllWindows()