import cv2
import numpy as np
import face_recognition
import pickle
import os
import mediapipe as mp
from collections import defaultdict
from deepface import DeepFace
import time
import threading
from queue import Queue, Empty
import traceback
import random

"""
Optimized Combined Vision System with Improved Face Tracking

Fixes:
- Prevents single face from being detected as multiple faces
- Better position tracking with overlap detection
- Face merging for duplicate detections
- Improved face persistence
"""

# === Configuration ===
DB_PATH = "../Resources/emoface.pkl"
TOLERANCE = 0.6
MAX_QUEUE_SIZE = 2
POSITION_MARGIN = 80  # Increased margin for better tracking
RECOGNITION_INTERVAL = 15.0  # Longer interval since we recognize once
OVERLAP_THRESHOLD = 0.6  # IoU threshold for duplicate face detection

# === Face Recognition DB ===
known_names = []
known_encodings = []
face_encodings_dict = {}

def load_db():
    global known_names, known_encodings, face_encodings_dict
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'rb') as f:
                known_names, known_encodings = pickle.load(f)
            face_encodings_dict = {name: encoding for name, encoding in zip(known_names, known_encodings)}
        except Exception:
            pass

def save_face_to_db(name, encoding):
    """Save new face to database"""
    global known_names, known_encodings, face_encodings_dict
    try:
        known_names.append(name)
        known_encodings.append(encoding)
        face_encodings_dict[name] = encoding
        
        with open(DB_PATH, 'wb') as f:
            pickle.dump((known_names, known_encodings), f)
    except Exception:
        pass

def recognize_face_once(encoding):
    """Recognize face once and return name or generate new ID"""
    if not known_encodings:
        return generate_face_id(), True
    
    try:
        matches = face_recognition.compare_faces(known_encodings, encoding, tolerance=TOLERANCE)
        if True in matches:
            face_distances = face_recognition.face_distance(known_encodings, encoding)
            best_match_idx = np.argmin(face_distances)
            if matches[best_match_idx]:
                return known_names[best_match_idx], False
    except Exception:
        pass
    
    return generate_face_id(), True

def generate_face_id():
    """Generate unique face ID"""
    return f"face_{random.randint(1000, 9999)}"

def detect_emotion(face_crop):
    try:
        if face_crop.shape[0] < 20 or face_crop.shape[1] < 20:
            return "Unknown"
        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        result = DeepFace.analyze(face_rgb, actions=['emotion'], enforce_detection=False, silent=True)
        if isinstance(result, list):
            return result[0]['dominant_emotion']
        else:
            return result['dominant_emotion']
    except Exception:
        return "Unknown"

def calculate_iou(box1, box2):
    """Calculate Intersection over Union for two bounding boxes"""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # Calculate intersection area
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    inter_width = max(0, inter_x_max - inter_x_min)
    inter_height = max(0, inter_y_max - inter_y_min)
    intersection = inter_width * inter_height
    
    # Calculate union area
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

# === Worker Threads ===
def face_recognition_worker(face_queue, result_queue, stop_event):
    """Worker thread for one-time face recognition"""
    while not stop_event.is_set():
        try:
            task = face_queue.get(timeout=0.5)
            if task is None:
                break
                
            face_id, face_crop, position_key, timestamp = task
            
            try:
                if face_crop.size == 0:
                    continue
                    
                small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
                face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
                face_encodings = face_recognition.face_encodings(face_crop_rgb)
                
                if face_encodings:
                    encoding = face_encodings[0]
                    name, is_new = recognize_face_once(encoding)
                    
                    if is_new and name.startswith("face_"):
                        save_face_to_db(name, encoding)
                    
                    result_queue.put(('recognition', face_id, name, is_new, position_key, timestamp))
                else:
                    result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
                
            except Exception:
                result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
            
            face_queue.task_done()
            
        except Empty:
            continue
        except Exception:
            pass

def emotion_detection_worker(emotion_queue, result_queue, stop_event):
    """Worker thread for emotion detection processing"""
    while not stop_event.is_set():
        try:
            task = emotion_queue.get(timeout=0.5)
            if task is None:
                break
                
            face_id, face_crop, timestamp = task
            
            try:
                if face_crop.size == 0:
                    continue
                    
                emotion_face = cv2.resize(face_crop, (64, 64))
                emotion = detect_emotion(emotion_face)
                
                result_queue.put(('emotion', face_id, emotion, timestamp))
                
            except Exception:
                result_queue.put(('emotion', face_id, "Unknown", timestamp))
            
            emotion_queue.task_done()
            
        except Empty:
            continue
        except Exception:
            pass

def gesture_recognition_worker(gesture_queue, result_queue, stop_event, gesture_names):
    """Worker thread for gesture recognition processing"""
    while not stop_event.is_set():
        try:
            task = gesture_queue.get(timeout=0.5)
            if task is None:
                break
                
            landmarks, hand_type, timestamp = task
            
            try:
                gesture_id = recognize_gesture_fast(landmarks)
                gesture_name = gesture_names[gesture_id]
                
                result_queue.put(('gesture', hand_type, gesture_name, timestamp))
                
            except Exception:
                result_queue.put(('gesture', hand_type, "Unknown", timestamp))
            
            gesture_queue.task_done()
            
        except Empty:
            continue
        except Exception:
            pass

def recognize_gesture_fast(landmarks):
    """Fast gesture recognition"""
    try:
        finger_pattern = get_finger_states_fast(landmarks)
        
        gesture_patterns = {
            (True, False, False, False, False): check_thumb_direction(landmarks),
            (False, False, False, False, False): 5,  # Fist
            (True, True, True, True, True): 6,      # Open hand
            (False, True, False, False, False): 7,  # Pointing
        }
        
        return gesture_patterns.get(finger_pattern, 0)
    except Exception:
        return 0

def get_finger_states_fast(landmarks):
    """Fast finger state detection"""
    fingers = []
    
    # Thumb
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    palm_center = landmarks[9]
    
    thumb_tip_distance = ((thumb_tip.x - palm_center.x)**2 + (thumb_tip.y - palm_center.y)**2)**0.5
    thumb_ip_distance = ((thumb_ip.x - palm_center.x)**2 + (thumb_ip.y - palm_center.y)**2)**0.5
    fingers.append(thumb_tip_distance > thumb_ip_distance)
    
    # Other fingers
    finger_tip_ids = [8, 12, 16, 20]
    finger_pip_ids = [6, 10, 14, 18]
    finger_mcp_ids = [5, 9, 13, 17]
    
    for i in range(4):
        tip_y = landmarks[finger_tip_ids[i]].y
        pip_y = landmarks[finger_pip_ids[i]].y
        mcp_y = landmarks[finger_mcp_ids[i]].y
        fingers.append(tip_y < pip_y and tip_y < mcp_y)
    
    return tuple(fingers)

def check_thumb_direction(landmarks):
    """Check for thumbs up vs thumbs down"""
    thumb_tip_y = landmarks[4].y
    wrist_y = landmarks[0].y
    return 1 if thumb_tip_y < wrist_y else 2

# === Improved Face Cache with Duplicate Detection ===
class ImprovedFaceCache:
    def __init__(self):
        self.faces = {}
        self.position_to_face = {}
        self.next_id = 0
        self.lock = threading.Lock()
        
    def get_position_key(self, x_center, y_center):
        """Create position key with larger margin for better tracking"""
        x_key = (x_center // POSITION_MARGIN) * POSITION_MARGIN
        y_key = (y_center // POSITION_MARGIN) * POSITION_MARGIN
        return f"{x_key}_{y_key}"
        
    def find_existing_face(self, x_center, y_center, box):
        """Find if this face already exists (duplicate detection)"""
        current_time = time.time()
        position_key = self.get_position_key(x_center, y_center)
        
        # First check by position key
        if position_key in self.position_to_face:
            face_id = self.position_to_face[position_key]
            if face_id in self.faces:
                face_data = self.faces[face_id]
                # Check if this face was seen recently
                if current_time - face_data['last_seen'] < 2.0:  # 2 seconds
                    return face_id
        
        # Then check by bounding box overlap (IoU)
        for face_id, face_data in self.faces.items():
            if current_time - face_data['last_seen'] < 2.0:  # Only check recent faces
                existing_box = face_data['box']
                iou = calculate_iou(box, existing_box)
                if iou > OVERLAP_THRESHOLD:
                    return face_id
        
        return None
        
    def get_face_id(self, x_center, y_center, box):
        with self.lock:
            current_time = time.time()
            
            # Check if this is a duplicate detection
            existing_face_id = self.find_existing_face(x_center, y_center, box)
            if existing_face_id is not None:
                # Update existing face
                self.faces[existing_face_id]['x'] = x_center
                self.faces[existing_face_id]['y'] = y_center
                self.faces[existing_face_id]['box'] = box
                self.faces[existing_face_id]['last_seen'] = current_time
                
                # Update position mapping
                position_key = self.get_position_key(x_center, y_center)
                old_position = self.faces[existing_face_id].get('position_key')
                if old_position in self.position_to_face:
                    del self.position_to_face[old_position]
                self.position_to_face[position_key] = existing_face_id
                self.faces[existing_face_id]['position_key'] = position_key
                
                return existing_face_id
            
            # Create new face
            face_id = self.next_id
            self.next_id += 1
            
            position_key = self.get_position_key(x_center, y_center)
            
            self.faces[face_id] = {
                'x': x_center, 
                'y': y_center,
                'position_key': position_key,
                'box': box,
                'name': "Recognizing...",  # Temporary name
                'emotion': "Unknown",
                'gesture': "Unknown",
                'last_recognition': 0,
                'last_emotion': 0,
                'last_seen': current_time,
                'recognition_attempted': False
            }
            
            self.position_to_face[position_key] = face_id
            
            return face_id
    
    def update_face_name(self, face_id, name, position_key):
        """Update face name and maintain position mapping"""
        with self.lock:
            if face_id in self.faces:
                old_position = self.faces[face_id].get('position_key')
                self.faces[face_id]['name'] = name
                self.faces[face_id]['last_recognition'] = time.time()
                self.faces[face_id]['recognition_attempted'] = True
                
                # Update position mapping
                if old_position in self.position_to_face:
                    del self.position_to_face[old_position]
                self.position_to_face[position_key] = face_id
                self.faces[face_id]['position_key'] = position_key
    
    def update_face(self, face_id, field, value):
        with self.lock:
            if face_id in self.faces:
                self.faces[face_id][field] = value
                if field == 'emotion':
                    self.faces[face_id]['last_emotion'] = time.time()
    
    def update_face_box(self, face_id, box):
        """Update face bounding box coordinates"""
        with self.lock:
            if face_id in self.faces:
                self.faces[face_id]['box'] = box
    
    def get_face_data(self, face_id):
        with self.lock:
            return self.faces.get(face_id, {}).copy()
    
    def get_all_faces(self):
        with self.lock:
            return {fid: data.copy() for fid, data in self.faces.items()}
    
    def needs_recognition(self, face_id):
        """Check if face needs recognition"""
        with self.lock:
            if face_id not in self.faces:
                return False
            
            face_data = self.faces[face_id]
            current_time = time.time()
            
            return (not face_data.get('recognition_attempted', False) or 
                   current_time - face_data.get('last_recognition', 0) > RECOGNITION_INTERVAL)
    
    def cleanup_old_faces(self, timeout=5.0):
        """Cleanup faces that haven't been seen for a while"""
        with self.lock:
            current_time = time.time()
            to_remove = []
            
            for face_id, face_data in self.faces.items():
                if current_time - face_data['last_seen'] > timeout:
                    to_remove.append(face_id)
            
            for face_id in to_remove:
                position_key = self.faces[face_id].get('position_key')
                if position_key in self.position_to_face:
                    del self.position_to_face[position_key]
                del self.faces[face_id]

# === Improved Vision System ===
class ImprovedVisionSystem:
    def __init__(self):
        load_db()
        
        # Initialize MediaPipe with better settings
        try:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=2,  # Limit to prevent too many detections
                refine_landmarks=False,
                min_detection_confidence=0.7,  # Higher confidence
                min_tracking_confidence=0.7
            )
        except Exception as e:
            raise
        
        try:
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                model_complexity=0,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                max_num_hands=1
            )
        except Exception as e:
            raise
        
        # Queues
        self.face_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.emotion_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.gesture_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.result_queue = Queue()
        self.stop_event = threading.Event()
        
        # Improved face cache
        self.face_cache = ImprovedFaceCache()
        
        # Gesture tracking
        self.gesture_names = {
            0: "Unknown", 1: "Thumbs Up", 2: "Thumbs Down",
            5: "Rock/Fist", 6: "Open Hand", 7: "Pointing"
        }
        self.hand_gesture = "Unknown"
        
        # Start worker threads
        self.threads = []
        self.start_workers()
        
    def start_workers(self):
        t = threading.Thread(target=face_recognition_worker, 
                           args=(self.face_queue, self.result_queue, self.stop_event),
                           name="FaceRecognition")
        t.daemon = True
        t.start()
        self.threads.append(t)
        
        t = threading.Thread(target=emotion_detection_worker, 
                           args=(self.emotion_queue, self.result_queue, self.stop_event),
                           name="EmotionDetection")
        t.daemon = True
        t.start()
        self.threads.append(t)
        
        t = threading.Thread(target=gesture_recognition_worker,
                           args=(self.gesture_queue, self.result_queue, self.stop_event, self.gesture_names),
                           name="GestureRecognition")
        t.daemon = True
        t.start()
        self.threads.append(t)
    
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
            except Exception:
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
        except Exception:
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
            
        except Exception:
            pass
    
    def get_all_detected_data(self):
        """Get all detected faces with coordinates"""
        data = {
            'faces': []
        }
        
        all_faces = self.face_cache.get_all_faces()
        for face_id, face_data in all_faces.items():
            data['faces'].append({
                'id': face_id,
                'name': face_data.get('name', 'Recognizing...'),
                'emotion': face_data.get('emotion', 'Unknown'),
                'gesture': face_data.get('gesture', 'Unknown'),
                'center_x': face_data.get('x', 0),
                'center_y': face_data.get('y', 0),
                'box': face_data.get('box', (0, 0, 0, 0))
            })
        
        return data
    
    def print_detected_data(self):
        """Print all detected data in readable format"""
        data = self.get_all_detected_data()
        
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
        
        print("="*60 + "\n")
    
    def process_frame(self, frame):
        """Process single frame with duplicate detection"""
        try:
            current_time = time.time()
            h, w = frame.shape[:2]
            
            # Process results from workers
            self.process_results()
            
            # Convert to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process faces
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
                        
                        # Use improved face tracking with duplicate detection
                        face_id = self.face_cache.get_face_id(x_center, y_center, box)
                        
                        face_data = self.face_cache.get_face_data(face_id)
                        face_crop = frame[y_min:y_max, x_min:x_max]
                        
                        if face_crop.size > 0:
                            # ONE-TIME RECOGNITION
                            if (self.face_cache.needs_recognition(face_id) and 
                                not self.face_queue.full()):
                                try:
                                    position_key = self.face_cache.get_position_key(x_center, y_center)
                                    self.face_queue.put_nowait((face_id, face_crop.copy(), position_key, current_time))
                                except:
                                    pass
                            
                            # Emotion detection
                            if (current_time - face_data.get('last_emotion', 0) > 5.0 and
                                not self.emotion_queue.full()):
                                try:
                                    self.emotion_queue.put_nowait((face_id, face_crop.copy(), current_time))
                                except:
                                    pass
                        
                        # Draw face info
                        face_data = self.face_cache.get_face_data(face_id)
                        self.draw_face_info(frame, x_min, y_min, x_max, y_max, face_data)
            except Exception:
                pass
            
            # Process hands (unchanged)
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
            except Exception:
                pass
            
            return frame
            
        except Exception:
            return frame
    
    def run(self):
        """Main run loop"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            return
        
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        frame_count = 0
        last_print_time = time.time()
        auto_print_interval = 5
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                
                processed_frame = self.process_frame(frame)
                
                if frame_count % 30 == 0:
                    self.face_cache.cleanup_old_faces()
                
                if time.time() - last_print_time > auto_print_interval:
                    data = self.get_all_detected_data()
                    if data['faces']:
                        self.print_detected_data()
                    last_print_time = time.time()
                
                cv2.imshow('Improved Vision System', processed_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    self.hand_gesture = "Unknown"
                elif key == ord('p'):
                    self.print_detected_data()
        
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup(cap)
    
    def cleanup(self, cap):
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
        
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        system = ImprovedVisionSystem()
        system.run()
    except Exception:
        pass