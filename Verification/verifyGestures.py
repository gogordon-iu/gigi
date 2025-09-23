import cv2
import mediapipe as mp
import numpy as np
import math
import threading
import time
from queue import Queue, Empty
from collections import defaultdict

class OptimizedHandGestureRecognizer:
    def __init__(self):
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.mp_hands = mp.solutions.hands
        
        # Initialize hands detector with optimized settings for speed
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            model_complexity=0,  # Fastest model
            min_detection_confidence=0.7,  # Lower for speed
            min_tracking_confidence=0.5,   # Lower for speed
            max_num_hands=2  # Allow both hands for left/right detection
        )
        
        # Define gesture names
        self.gesture_names = {
            0: "Unknown",
            1: "Thumbs Up",
            2: "Thumbs Down", 
            5: "Rock/Fist",
            6: "Open Hand",
            7: "Pointing",
        }
        
        # Optimization - cache landmark indices
        self.finger_tip_ids = [4, 8, 12, 16, 20]
        self.finger_pip_ids = [3, 6, 10, 14, 18]
        self.finger_mcp_ids = [2, 5, 9, 13, 17]
        
        # Threading configuration
        self.MAX_QUEUE_SIZE = 3
        self.gesture_queue = Queue(maxsize=self.MAX_QUEUE_SIZE)
        self.result_queue = Queue()
        self.stop_event = threading.Event()
        self.current_gesture = "Unknown"
        self.current_hand_type = ""
        
        # Hand state tracking for both hands
        self.left_hand_gesture = "Unknown"
        self.right_hand_gesture = "Unknown"
        
        # Performance tracking
        self.gesture_counter = defaultdict(int)
        self.last_recognition_time = 0
        self.recognition_interval = 0.5  # Process gesture every 0.5 seconds
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self.gesture_worker, daemon=True)
        self.worker_thread.start()
    
    def gesture_worker(self):
        """Worker thread for gesture recognition processing"""
        while not self.stop_event.is_set():
            try:
                task = self.gesture_queue.get(timeout=0.1)
                if task is None:
                    # Sentinel to stop worker
                    break
                
                landmarks, hand_type, timestamp = task
                
                try:
                    # Recognize gesture
                    gesture_id = self.recognize_gesture_fast(landmarks)
                    gesture_name = self.gesture_names[gesture_id]
                    
                    # Update counters
                    if gesture_name != "Unknown":
                        self.gesture_counter[gesture_name] += 1
                    
                    # Send result back
                    self.result_queue.put((gesture_name, hand_type, timestamp))
                    
                except Exception as e:
                    print(f"[ERROR] Gesture recognition failed: {str(e)}")
                    self.result_queue.put(("Unknown", hand_type, timestamp))
                
                self.gesture_queue.task_done()
                
            except Empty:
                continue
            except Exception as e:
                print(f"[ERROR] Gesture worker error: {str(e)}")
    
    def get_finger_states_fast(self, landmarks):
        """Ultra-fast finger state detection with improved fist detection"""
        fingers = []
        
        # Thumb - improved check for fist detection
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        
        # For fist: thumb tip should be closer to palm than thumb IP
        # For extended: thumb tip should be further from palm than thumb IP
        palm_center = landmarks[9]  # Middle finger MCP as palm reference
        
        thumb_tip_distance = ((thumb_tip.x - palm_center.x)**2 + (thumb_tip.y - palm_center.y)**2)**0.5
        thumb_ip_distance = ((thumb_ip.x - palm_center.x)**2 + (thumb_ip.y - palm_center.y)**2)**0.5
        
        # Thumb is extended if tip is further from palm than IP joint
        fingers.append(thumb_tip_distance > thumb_ip_distance)
        
        # Other fingers - improved detection
        for i in range(1, 5):
            tip_y = landmarks[self.finger_tip_ids[i]].y
            pip_y = landmarks[self.finger_pip_ids[i]].y
            mcp_y = landmarks[self.finger_mcp_ids[i]].y
            
            # Finger is extended if tip is above both pip and mcp
            fingers.append(tip_y < pip_y and tip_y < mcp_y)
        
        return tuple(fingers)  # Return as tuple for faster comparison
    
    def recognize_gesture_fast(self, landmarks):
        """Ultra-fast gesture recognition with lookup table"""
        finger_pattern = self.get_finger_states_fast(landmarks)
        
        # Fast lookup dictionary for common patterns
        gesture_patterns = {
            (True, False, False, False, False): self._check_thumb_direction(landmarks),
            (False, False, False, False, False): 5,  # Fist
            (True, True, True, True, True): 6,      # Open hand
            (False, True, False, False, False): 7,  # Pointing
        }
        
        return gesture_patterns.get(finger_pattern, 0)  # Default to Unknown
    
    def _check_thumb_direction(self, landmarks):
        """Quick check for thumbs up vs thumbs down"""
        thumb_tip_y = landmarks[4].y
        wrist_y = landmarks[0].y
        return 1 if thumb_tip_y < wrist_y else 2
    
    def process_results(self):
        """Process results from worker thread (non-blocking)"""
        while True:
            try:
                result = self.result_queue.get_nowait()
                gesture_name, hand_type, timestamp = result
                
                # Update hand-specific gestures
                if hand_type == "Left":
                    self.left_hand_gesture = gesture_name
                elif hand_type == "Right":
                    self.right_hand_gesture = gesture_name
                
                self.current_gesture = gesture_name
                self.current_hand_type = hand_type
                self.last_recognition_time = timestamp
            except Empty:
                break
    
    def draw_optimized_landmarks(self, image, hand_landmarks):
        """Draw simplified landmarks for better performance"""
        # Only draw key points instead of all connections
        h, w, _ = image.shape
        
        # Draw only fingertips and palm
        key_points = [4, 8, 12, 16, 20, 0]  # Tips + wrist
        for idx in key_points:
            landmark = hand_landmarks.landmark[idx]
            cx, cy = int(landmark.x * w), int(landmark.y * h)
            cv2.circle(image, (cx, cy), 5, (0, 255, 0), -1)
    
    def check_happy_gesture(self):
        """Check if both hands are showing open hand or fist (happy gesture)"""
        happy_gestures = ["Open Hand", "Rock/Fist"]
        
        left_is_happy = self.left_hand_gesture in happy_gestures
        right_is_happy = self.right_hand_gesture in happy_gestures
        
        return left_is_happy and right_is_happy
    
    def draw_gesture_info_fast(self, image, hand_landmarks, hand_type, gesture):
        """Fixed gesture info drawing with proper text sizing and positioning"""
        if not hand_landmarks:
            return
        
        h, w, _ = image.shape
        
        # Create display text
        display_text = f"{hand_type}: {gesture}"
        
        # Get text dimensions for proper sizing
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 2
        
        (text_width, text_height), baseline = cv2.getTextSize(display_text, font, font_scale, font_thickness)
        
        # Add padding
        padding = 10
        box_width = text_width + (padding * 2)
        box_height = text_height + baseline + (padding * 2)
        
        # Determine position based on hand type
        if hand_type == "Right":
            # Right hand info on right side
            x_pos = w - box_width - 10
        else:
            # Left hand info on left side
            x_pos = 10
        
        # Position vertically
        y_pos = 50
        
        # Draw background rectangle with proper sizing
        cv2.rectangle(image, 
                     (x_pos, y_pos - box_height), 
                     (x_pos + box_width, y_pos), 
                     (0, 0, 0), -1)
        
        # Draw white border
        cv2.rectangle(image, 
                     (x_pos, y_pos - box_height), 
                     (x_pos + box_width, y_pos), 
                     (255, 255, 255), 2)
        
        # Draw text with proper positioning
        text_x = x_pos + padding
        text_y = y_pos - padding - baseline
        
        cv2.putText(image, display_text,
                   (text_x, text_y),
                   font, font_scale, (255, 255, 255), font_thickness)
    
    def draw_happy_message(self, image):
        """Draw happy message when both hands show open hand or fist"""
        h, w, _ = image.shape
        
        # Happy message text
        happy_text = "HAPPY! :)"
        
        # Get text dimensions
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.5
        font_thickness = 3
        
        (text_width, text_height), baseline = cv2.getTextSize(happy_text, font, font_scale, font_thickness)
        
        # Center position
        x_center = (w - text_width) // 2
        y_center = h // 2
        
        # Add padding
        padding = 20
        box_width = text_width + (padding * 2)
        box_height = text_height + baseline + (padding * 2)
        
        # Draw background
        cv2.rectangle(image, 
                     (x_center - padding, y_center - text_height - padding), 
                     (x_center + text_width + padding, y_center + baseline + padding), 
                     (0, 255, 0), -1)
        
        # Draw border
        cv2.rectangle(image, 
                     (x_center - padding, y_center - text_height - padding), 
                     (x_center + text_width + padding, y_center + baseline + padding), 
                     (255, 255, 255), 3)
        
        # Draw text
        cv2.putText(image, happy_text,
                   (x_center, y_center),
                   font, font_scale, (0, 0, 0), font_thickness)
    
    def draw_gesture_stats(self, image):
        """Draw gesture statistics in bottom corner"""
        h, w, _ = image.shape
        
        # Position for stats
        start_y = h - 120
        x_pos = 10
        
        # Draw background for stats
        cv2.rectangle(image, (x_pos, start_y - 10), (x_pos + 200, h - 10), (50, 50, 50), -1)
        cv2.rectangle(image, (x_pos, start_y - 10), (x_pos + 200, h - 10), (255, 255, 255), 2)
            
        # Draw current gestures
        y_offset = 30
        cv2.putText(image, f"Left: {self.left_hand_gesture}", 
                   (x_pos + 5, start_y + y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        y_offset += 20
        cv2.putText(image, f"Right: {self.right_hand_gesture}", 
                   (x_pos + 5, start_y + y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    
    def process_frame_optimized(self, image):
        """Optimized frame processing with threading"""
        current_time = time.time()
        
        # Flip image for proper handedness
        image = cv2.flip(image, 1)
        
        # Resize for faster processing
        processing_image = cv2.resize(image, (320, 240))
        
        # Convert to RGB
        rgb_image = cv2.cvtColor(processing_image, cv2.COLOR_BGR2RGB)
        rgb_image.flags.writeable = False
        
        # Process with MediaPipe
        results = self.hands.process(rgb_image)
        
        # Process results from worker thread
        self.process_results()
        
        if results.multi_hand_landmarks and results.multi_handedness:
            # Process all detected hands
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                hand_type = handedness.classification[0].label
                
                # Scale landmarks back to original size
                scaled_landmarks = []
                scale_x = image.shape[1] / 320
                scale_y = image.shape[0] / 240
                
                for lm in hand_landmarks.landmark:
                    scaled_lm = type('obj', (object,), {
                        'x': lm.x * scale_x / image.shape[1],
                        'y': lm.y * scale_y / image.shape[0]
                    })()
                    scaled_landmarks.append(scaled_lm)
                
                # Create scaled hand landmarks object
                scaled_hand_landmarks = type('obj', (object,), {'landmark': scaled_landmarks})()
                
                # Draw optimized landmarks
                self.draw_optimized_landmarks(image, scaled_hand_landmarks)
                
                # Queue gesture recognition task (non-blocking)
                if (current_time - self.last_recognition_time > self.recognition_interval and
                    not self.gesture_queue.full()):
                    try:
                        self.gesture_queue.put_nowait((scaled_landmarks, hand_type, current_time))
                    except:
                        pass  # Queue full, skip
                
                # Get current gesture for this hand
                current_hand_gesture = self.left_hand_gesture if hand_type == "Left" else self.right_hand_gesture
                
                # Draw gesture info with proper sizing
                self.draw_gesture_info_fast(image, scaled_hand_landmarks, hand_type, current_hand_gesture)
        
        # Check and display happy message if both hands are showing open hand or fist
        if self.check_happy_gesture():
            self.draw_happy_message(image)
        
        # Draw gesture statistics
        self.draw_gesture_stats(image)
        
        return image
    
    def run_webcam_optimized(self):
        """Optimized webcam processing with threading"""
        cap = cv2.VideoCapture(0)
        
        # Camera optimization
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Performance tracking (simplified)
        fps_count = 0
        fps_start = time.time()
        frame_skip = 0
        
        print("[INFO] Starting optimized hand gesture recognition...")
        print("[INFO] Controls: 'q' to quit, 'r' to reset stats")
        print("[INFO] Show both hands with open palms or fists for HAPPY message!")
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    continue
                
                fps_count += 1
                
                # Skip frames for performance if needed
                if frame_skip > 0:
                    frame_skip -= 1
                    continue
                
                # Process frame
                processed_frame = self.process_frame_optimized(frame)
                
                # Auto-adjust frame skipping based on performance (simplified)
                if fps_count >= 30:
                    fps = fps_count / (time.time() - fps_start)
                    fps_count = 0
                    fps_start = time.time()
                    
                    if fps < 15:
                        frame_skip = 1
                    elif fps > 25:
                        frame_skip = 0
                
                
                # Display frame
                cv2.imshow('Hand Gesture Recognition', processed_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    self.gesture_counter.clear()
                    self.left_hand_gesture = "Unknown"
                    self.right_hand_gesture = "Unknown"
                    print("[INFO] Reset gesture counters")
                
        except KeyboardInterrupt:
            print("\n[INFO] Stopping...")
        
        finally:
            # Simple cleanup
            self.stop_event.set()
            cap.release()
            cv2.destroyAllWindows()

def main():
    """Main function"""
    try:
        recognizer = OptimizedHandGestureRecognizer()
        recognizer.run_webcam_optimized()
    except Exception as e:
        print(f"[ERROR] Application error: {str(e)}")

if __name__ == "__main__":
    main()