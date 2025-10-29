import cv2
import time
import threading
from queue import Queue, Empty
import vision_helper as vh

class Vision:
    def __init__(self):
        # Initialize all components but don't start workers until needed
        self.face_db = vh.FaceDatabase()
        self.emotion_detector = vh.EmotionDetector()
        self.face_cache = vh.ImprovedFaceCache()
        
        # Data structure accessible across class
        self.detection_data = {
            'faces': [],
            'gestures': [],
            'last_updated': time.time()
        }
        
        # MediaPipe components (initialized on first use)
        self.face_mesh = None
        self.hands = None
        
        # Queues and threading
        self.face_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.emotion_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.gesture_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.result_queue = Queue()
        self.stop_event = threading.Event()
        
        # Gesture configuration
        self.gesture_names = {
            0: "Unknown", 1: "Thumbs Up", 2: "Thumbs Down",
            5: "Rock/Fist", 6: "Open Hand", 7: "Pointing"
        }
        self.hand_gesture = "Unknown"
        
        # Track which workers are running
        self.active_workers = {
            'face_recognition': False,
            'emotion': False,
            'gesture': False
        }
        
        self.threads = []
    
    def start_worker_if_needed(self, worker_type):
        """Start specific worker thread if not already running"""
        if self.active_workers[worker_type]:
            return
        
        if worker_type == 'face_recognition' and not self.active_workers['face_recognition']:
            t = threading.Thread(target=vh.face_recognition_worker, 
                               args=(self.face_queue, self.result_queue, self.stop_event, self.face_db),
                               name="FaceRecognition")
            t.daemon = True
            t.start()
            self.threads.append(t)
            self.active_workers['face_recognition'] = True
        
        elif worker_type == 'emotion' and not self.active_workers['emotion']:
            t = threading.Thread(target=vh.emotion_detection_worker, 
                               args=(self.emotion_queue, self.result_queue, self.stop_event, self.emotion_detector),
                               name="EmotionDetection")
            t.daemon = True
            t.start()
            self.threads.append(t)
            self.active_workers['emotion'] = True
        
        elif worker_type == 'gesture' and not self.active_workers['gesture']:
            t = threading.Thread(target=vh.gesture_recognition_worker,
                               args=(self.gesture_queue, self.result_queue, self.stop_event, self.gesture_names),
                               name="GestureRecognition")
            t.daemon = True
            t.start()
            self.threads.append(t)
            self.active_workers['gesture'] = True
    
    def initialize_face_detection(self):
        """Initialize face detection components if not already initialized"""
        if self.face_mesh is None:
            self.face_mesh = vh.MediaPipeInitializers.initialize_face_mesh()
    
    def initialize_gesture_detection(self):
        """Initialize gesture detection components if not already initialized"""
        if self.hands is None:
            self.hands = vh.MediaPipeInitializers.initialize_hands()
    
    def process_results(self):
        """Process results from all worker threads"""
        while True:
            try:
                result = self.result_queue.get_nowait()
                
                if result[0] == 'recognition':
                    _, face_id, name, is_new, position_key, timestamp = result
                    self.face_cache.update_face_name(face_id, name, position_key)
                    
                elif result[0] == 'emotion':
                    _, face_id, emotion, timestamp = result
                    self.face_cache.update_face(face_id, 'emotion', emotion)
                        
                elif result[0] == 'gesture':
                    _, hand_type, gesture_name, timestamp = result
                    self.hand_gesture = gesture_name
                
            except Empty:
                break
            except Exception as e:
                print(f"Error processing results: {e}")
                break
    
    def associate_gesture_to_face(self, hand_x, hand_y, w, h):
        """Associate gesture to nearest face"""
        try:
            min_distance = float('inf')
            closest_face_id = None
            
            all_faces = self.face_cache.get_all_faces()
            for face_id, face_data in all_faces.items():
                face_x = face_data['x'] / w
                face_y = face_data['y'] / h
                
                distance = ((hand_x - face_x)**2 + (hand_y - face_y)**2)**0.5
                
                if distance < min_distance and distance < 0.3:
                    min_distance = distance
                    closest_face_id = face_id
            
            return closest_face_id
        except Exception as e:
            return None
    
    def draw_face_info(self, frame, x_min, y_min, x_max, y_max, face_data):
        """Draw face bounding box and info"""
        try:
            # Draw rectangle
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 2)
            
            # Get coordinates
            x_center = face_data.get('x', 0)
            y_center = face_data.get('y', 0)
            
            # Draw crosshair at face center
            crosshair_size = 10
            cv2.line(frame, (x_center - crosshair_size, y_center), 
                    (x_center + crosshair_size, y_center), (0, 255, 255), 2)
            cv2.line(frame, (x_center, y_center - crosshair_size), 
                    (x_center, y_center + crosshair_size), (0, 255, 255), 2)
            cv2.circle(frame, (x_center, y_center), 3, (0, 255, 255), -1)
            
            # Prepare label with coordinates
            name = face_data.get('name', 'Recognizing...')
            emotion = face_data.get('emotion', 'Unknown')
            gesture = face_data.get('gesture', 'Unknown')
            
            # Main label (name, emotion, gesture)
            label = f"{name}"
            if emotion != 'Unknown':
                label += f" | {emotion}"
            if gesture != 'Unknown':
                label += f" | {gesture}"
            
            # Coordinates label
            coord_label = f"({x_center}, {y_center})"
            
            # Draw main label with background
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            # Draw main label background and text
            cv2.rectangle(frame, (x_min, y_min - text_height - 10), 
                         (x_min + text_width, y_min), (0, 255, 255), -1)
            cv2.putText(frame, label, (x_min, y_min - 5), 
                       font, font_scale, (0, 0, 0), thickness)
            
            # Draw coordinates below the box
            (coord_width, coord_height), coord_baseline = cv2.getTextSize(coord_label, font, font_scale, thickness)
            cv2.rectangle(frame, (x_min, y_max), 
                         (x_min + coord_width, y_max + coord_height + 10), (0, 255, 255), -1)
            cv2.putText(frame, coord_label, (x_min, y_max + coord_height + 5), 
                       font, font_scale, (0, 0, 0), thickness)
            
        except Exception as e:
            print(f"Error drawing face info: {e}")
    
    def update_detection_data(self):
        """Update the main detection data structure"""
        self.detection_data['faces'] = []
        
        all_faces = self.face_cache.get_all_faces()
        for face_id, face_data in all_faces.items():
            self.detection_data['faces'].append({
                'id': face_id,
                'name': face_data.get('name', 'Recognizing...'),
                'emotion': face_data.get('emotion', 'Unknown'),
                'gesture': face_data.get('gesture', 'Unknown'),
                'center_x': face_data.get('x', 0),
                'center_y': face_data.get('y', 0),
                'box': face_data.get('box', (0, 0, 0, 0))
            })
        
        self.detection_data['gestures'] = [self.hand_gesture] if self.hand_gesture != "Unknown" else []
        self.detection_data['last_updated'] = time.time()
    
    def get_detection_data(self):
        """Get all detection data"""
        self.update_detection_data()
        return self.detection_data.copy()
    
    def print_detection_data(self):
        """Print all detected data in readable format"""
        data = self.get_detection_data()
        
        print("\n" + "="*60)
        print("DETECTED DATA:")
        print("="*60)
        
        if data['faces']:
            print(f"\nFACES ({len(data['faces'])} detected):")
            for face in data['faces']:
                print(f"  {face['name']}:")
                print(f"    Emotion: {face['emotion']}")
                print(f"    Gesture: {face['gesture']}")
                print(f"    Center: ({face['center_x']}, {face['center_y']})")
        else:
            print("\nFACES: None detected")
        
        if data['gestures']:
            print(f"\nGESTURES: {', '.join(data['gestures'])}")
        else:
            print("\nGESTURES: None detected")
        
        print("="*60 + "\n")
    
    def process_frame(self, frame, flags=None):
        """
        Main function to process frame with function-level flags
        
        Args:
            frame: Input image/frame
            flags: Dictionary of flags specifying what to process
                   Example: {
                       'face_detection': True,
                       'emotion': False, 
                       'gesture': True,
                       'face_recognition': True
                   }
        
        Returns:
            Processed frame and detection data
        """
        try:
            current_time = time.time()
            h, w = frame.shape[:2]
            
            # Default flags - only process what's explicitly requested
            default_flags = {
                'face_detection': False,
                'emotion': False,
                'gesture': False,
                'face_recognition': False
            }
            
            # Merge with provided flags
            if flags:
                for key in default_flags:
                    if key in flags:
                        default_flags[key] = flags[key]
            
            face_detection = default_flags['face_detection']
            emotion = default_flags['emotion']
            gesture = default_flags['gesture']
            face_recognition = default_flags['face_recognition']
            
            # Process results from workers (if any are running)
            self.process_results()
            
            # Convert to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process faces if requested
            if face_detection:
                self.initialize_face_detection()
                
                try:
                    face_results = self.face_mesh.process(rgb)
                    
                    if face_results.multi_face_landmarks:
                        for face_landmarks in face_results.multi_face_landmarks:
                            x_coords = [lm.x * w for lm in face_landmarks.landmark]
                            y_coords = [lm.y * h for lm in face_landmarks.landmark]
                            
                            x_min = max(int(min(x_coords)) - 30, 0)
                            x_max = min(int(max(x_coords)) + 30, w)
                            y_min = max(int(min(y_coords)) - 30, 0)
                            y_max = min(int(max(y_coords)) + 30, h)
                            
                            if x_max <= x_min or y_max <= y_min:
                                continue
                            
                            x_center = (x_min + x_max) // 2
                            y_center = (y_min + y_max) // 2
                            box = (x_min, y_min, x_max, y_max)
                            
                            face_id = self.face_cache.get_face_id(x_center, y_center, box)
                            
                            face_data = self.face_cache.get_face_data(face_id)
                            face_crop = frame[y_min:y_max, x_min:x_max]
                            
                            if face_crop.size > 0:
                                # Face recognition if requested
                                if face_recognition:
                                    self.start_worker_if_needed('face_recognition')
                                    if (self.face_cache.needs_recognition(face_id) and 
                                        not self.face_queue.full()):
                                        try:
                                            position_key = self.face_cache.get_position_key(x_center, y_center)
                                            self.face_queue.put_nowait((face_id, face_crop.copy(), position_key, current_time))
                                        except:
                                            pass
                                
                                # Emotion detection if requested
                                if emotion:
                                    self.start_worker_if_needed('emotion')
                                    if (current_time - face_data.get('last_emotion', 0) > 5.0 and
                                        not self.emotion_queue.full()):
                                        try:
                                            self.emotion_queue.put_nowait((face_id, face_crop.copy(), current_time))
                                        except:
                                            pass
                            
                            # Draw face info
                            face_data = self.face_cache.get_face_data(face_id)
                            self.draw_face_info(frame, x_min, y_min, x_max, y_max, face_data)
                except Exception as e:
                    print(f"Face processing error: {e}")
            
            # Process hands if requested
            if gesture:
                self.initialize_gesture_detection()
                self.start_worker_if_needed('gesture')
                
                try:
                    hand_results = self.hands.process(rgb)
                    
                    if hand_results.multi_hand_landmarks and hand_results.multi_handedness:
                        for hand_landmarks, handedness in zip(hand_results.multi_hand_landmarks, 
                                                              hand_results.multi_handedness):
                            hand_type = handedness.classification[0].label
                            
                            wrist = hand_landmarks.landmark[0]
                            hand_x = wrist.x
                            hand_y = wrist.y
                            
                            hand_x_pixel = int(hand_x * w)
                            hand_y_pixel = int(hand_y * h)
                            
                            key_points = [4, 8, 12, 16, 20, 0]
                            for idx in key_points:
                                landmark = hand_landmarks.landmark[idx]
                                cx, cy = int(landmark.x * w), int(landmark.y * h)
                                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
                            
                            if not self.gesture_queue.full():
                                try:
                                    landmarks = hand_landmarks.landmark
                                    self.gesture_queue.put_nowait((landmarks, hand_type, current_time))
                                except:
                                    pass
                            
                            closest_face_id = self.associate_gesture_to_face(hand_x, hand_y, w, h)
                            if closest_face_id is not None and self.hand_gesture != "Unknown":
                                self.face_cache.update_face(closest_face_id, 'gesture', self.hand_gesture)
                except Exception as e:
                    print(f"Hand processing error: {e}")
            
            # Cleanup old faces periodically
            if face_detection and current_time % 30 == 0:
                self.face_cache.cleanup_old_faces()
            
            # Update detection data
            self.update_detection_data()
            
            return frame, self.get_detection_data()
            
        except Exception as e:
            print(f"Frame processing error: {e}")
            return frame, self.get_detection_data()
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_event.set()
        
        for q in [self.face_queue, self.emotion_queue, self.gesture_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except:
                    break
        
        for _ in range(len(self.threads)):
            try:
                self.face_queue.put(None, timeout=0.1)
                self.emotion_queue.put(None, timeout=0.1)
                self.gesture_queue.put(None, timeout=0.1)
            except:
                pass
        
        for thread in self.threads:
            thread.join(timeout=1.0)
        
        cv2.destroyAllWindows()

# Example usage
if __name__ == "__main__":
    vision = Vision()
    
    cap = cv2.VideoCapture(0)
    
    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Example 1: Only face detection
            if frame_count % 90 == 0:  # Every 3 seconds at 30fps
                processed_frame, detection_data = vision.process_frame(frame, {
                    'face_detection': True,
                    'face_recognition': True,
                    'emotion': False,
                    'gesture': False
                })
                print("=== Face Detection Only ===")
                vision.print_detection_data()
            
            else:
                processed_frame = frame.copy()
            
            cv2.imshow('Vision System', processed_frame)
            
    
    finally:
        vision.cleanup()
        cap.release()