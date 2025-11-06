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
from pyzbar.pyzbar import decode

"""
Vision Helper - Contains all helper classes, detection functions, and worker threads
"""

# === Configuration ===
DB_PATH = "../Resources/emoface.pkl"
TOLERANCE = 0.6
MAX_QUEUE_SIZE = 2
POSITION_MARGIN = 80
RECOGNITION_INTERVAL = 15.0
OVERLAP_THRESHOLD = 0.6

# === Face Recognition DB ===
class FaceDatabase:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.known_names = []
        self.known_encodings = []
        self.face_encodings_dict = {}
        self.load_db()
    
    def load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    self.known_names, self.known_encodings = pickle.load(f)
                self.face_encodings_dict = {name: encoding for name, encoding in zip(self.known_names, self.known_encodings)}
            except Exception as e:
                print(f"Error loading database: {e}")
    
    def save_face_to_db(self, name, encoding):
        try:
            self.known_names.append(name)
            self.known_encodings.append(encoding)
            self.face_encodings_dict[name] = encoding
            
            with open(self.db_path, 'wb') as f:
                pickle.dump((self.known_names, self.known_encodings), f)
        except Exception as e:
            print(f"Error saving to database: {e}")
    
    def recognize_face_once(self, encoding, tolerance=TOLERANCE):
        if not self.known_encodings:
            return self.generate_face_id(), True
        
        try:
            matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=tolerance)
            if True in matches:
                face_distances = face_recognition.face_distance(self.known_encodings, encoding)
                best_match_idx = np.argmin(face_distances)
                if matches[best_match_idx]:
                    return self.known_names[best_match_idx], False
        except Exception as e:
            print(f"Error in face recognition: {e}")
        
        return self.generate_face_id(), True
    
    def generate_face_id(self):
        return f"face_{random.randint(1000, 9999)}"

# === Emotion Detection ===
class EmotionDetector:
    @staticmethod
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
        except Exception as e:
            return "Unknown"

# === Geometry Utilities ===
class GeometryUtils:
    @staticmethod
    def calculate_iou(box1, box2):
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        inter_width = max(0, inter_x_max - inter_x_min)
        inter_height = max(0, inter_y_max - inter_y_min)
        intersection = inter_width * inter_height
        
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0

# === Worker Threads ===
def face_recognition_worker(face_queue, result_queue, stop_event, face_db):
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
                    name, is_new = face_db.recognize_face_once(encoding)
                    
                    if is_new and name.startswith("face_"):
                        face_db.save_face_to_db(name, encoding)
                    
                    result_queue.put(('recognition', face_id, name, is_new, position_key, timestamp))
                else:
                    result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
                
            except Exception as e:
                result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
            
            face_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"Face recognition worker error: {e}")

def emotion_detection_worker(emotion_queue, result_queue, stop_event, emotion_detector):
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
                emotion = emotion_detector.detect_emotion(emotion_face)
                
                result_queue.put(('emotion', face_id, emotion, timestamp))
                
            except Exception as e:
                result_queue.put(('emotion', face_id, "Unknown", timestamp))
            
            emotion_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"Emotion detection worker error: {e}")

def gesture_recognition_worker(gesture_queue, result_queue, stop_event, gesture_names):
    while not stop_event.is_set():
        try:
            task = gesture_queue.get(timeout=0.5)
            if task is None:
                break
                
            landmarks, hand_type, timestamp = task
            
            try:
                gesture_id = GestureRecognizer.recognize_gesture_fast(landmarks)
                gesture_name = gesture_names[gesture_id]
                
                result_queue.put(('gesture', hand_type, gesture_name, timestamp))
                
            except Exception as e:
                result_queue.put(('gesture', hand_type, "Unknown", timestamp))
            
            gesture_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"Gesture recognition worker error: {e}")

# === Gesture Recognition ===
class GestureRecognizer:
    @staticmethod
    def recognize_gesture_fast(landmarks):
        try:
            finger_pattern = GestureRecognizer.get_finger_states_fast(landmarks)
            
            gesture_patterns = {
                (True, False, False, False, False): GestureRecognizer.check_thumb_direction(landmarks),
                (False, False, False, False, False): 5,  # Fist
                (True, True, True, True, True): 6,      # Open hand
                (False, True, False, False, False): 7,  # Pointing
            }
            
            return gesture_patterns.get(finger_pattern, 0)
        except Exception:
            return 0

    @staticmethod
    def get_finger_states_fast(landmarks):
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

    @staticmethod
    def check_thumb_direction(landmarks):
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
        x_key = (x_center // POSITION_MARGIN) * POSITION_MARGIN
        y_key = (y_center // POSITION_MARGIN) * POSITION_MARGIN
        return f"{x_key}_{y_key}"
        
    def find_existing_face(self, x_center, y_center, box):
        current_time = time.time()
        position_key = self.get_position_key(x_center, y_center)
        
        if position_key in self.position_to_face:
            face_id = self.position_to_face[position_key]
            if face_id in self.faces:
                face_data = self.faces[face_id]
                if current_time - face_data['last_seen'] < 2.0:
                    return face_id
        
        for face_id, face_data in self.faces.items():
            if current_time - face_data['last_seen'] < 2.0:
                existing_box = face_data['box']
                iou = GeometryUtils.calculate_iou(box, existing_box)
                if iou > OVERLAP_THRESHOLD:
                    return face_id
        
        return None
        
    def get_face_id(self, x_center, y_center, box):
        with self.lock:
            current_time = time.time()
            
            existing_face_id = self.find_existing_face(x_center, y_center, box)
            if existing_face_id is not None:
                self.faces[existing_face_id]['x'] = x_center
                self.faces[existing_face_id]['y'] = y_center
                self.faces[existing_face_id]['box'] = box
                self.faces[existing_face_id]['last_seen'] = current_time
                
                position_key = self.get_position_key(x_center, y_center)
                old_position = self.faces[existing_face_id].get('position_key')
                if old_position in self.position_to_face:
                    del self.position_to_face[old_position]
                self.position_to_face[position_key] = existing_face_id
                self.faces[existing_face_id]['position_key'] = position_key
                
                return existing_face_id
            
            face_id = self.next_id
            self.next_id += 1
            
            position_key = self.get_position_key(x_center, y_center)
            
            self.faces[face_id] = {
                'x': x_center, 
                'y': y_center,
                'position_key': position_key,
                'box': box,
                'name': "Recognizing...",
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
        with self.lock:
            if face_id in self.faces:
                old_position = self.faces[face_id].get('position_key')
                self.faces[face_id]['name'] = name
                self.faces[face_id]['last_recognition'] = time.time()
                self.faces[face_id]['recognition_attempted'] = True
                
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
        with self.lock:
            if face_id not in self.faces:
                return False
            
            face_data = self.faces[face_id]
            current_time = time.time()
            
            return (not face_data.get('recognition_attempted', False) or 
                   current_time - face_data.get('last_recognition', 0) > RECOGNITION_INTERVAL)
    
    def cleanup_old_faces(self, timeout=5.0):
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

# === MediaPipe Initializers ===
class MediaPipeInitializers:
    @staticmethod
    def initialize_face_mesh():
        try:
            mp_face_mesh = mp.solutions.face_mesh
            face_mesh = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=2,
                refine_landmarks=False,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            )
            return face_mesh
        except Exception as e:
            raise Exception(f"Failed to initialize face mesh: {e}")
    
    @staticmethod
    def initialize_hands():
        try:
            mp_hands = mp.solutions.hands
            hands = mp_hands.Hands(
                static_image_mode=False,
                model_complexity=0,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                max_num_hands=1
            )
            return hands
        except Exception as e:
            raise Exception(f"Failed to initialize hands: {e}")

# === Detection Functions ===
class DetectionFunctions:
    
    @staticmethod
    def detect_qr(frame, last_detection_data, verbose=False):
        """Detect QR codes in frame"""
        try:
            height, width = frame.shape[:2]
            decoded_objects = decode(frame)
            
            if decoded_objects:
                for obj in decoded_objects:
                    qr_data = obj.data.decode('utf-8')
                    center_x = obj.rect.left + obj.rect.width // 2
                    center_y = obj.rect.top + obj.rect.height // 2
                    
                    # Store in last_detection_data with unique ID
                    qr_id = f"qr_{qr_data}"
                    last_detection_data[qr_id] = {
                        'type': 'qr',
                        'data': qr_data,
                        'box': (obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height),
                        'center': (center_x, center_y),
                        'offset': (((width // 2) - center_x) / width, ((height // 2) - center_y) / height)
                    }
                    
                    if verbose:
                        print(f"QR Code detected: {qr_data}")
        
        except Exception as e:
            print(f"Error in QR detection: {e}")
    
    @staticmethod
    def detect_motion(frame, motion_state, last_detection_data, verbose=False):
        """Detect motion in frame"""
        try:
            height, width = frame.shape[:2]
            
            # Parameters
            blur_k = 21
            alpha = 0.02
            thr = 25
            min_area = 1000
            max_width = 800
            
            # Resize for speed
            scale = 1.0
            if width > max_width:
                scale = max_width / float(width)
            
            def resize_frame(f):
                if scale != 1.0:
                    return cv2.resize(f, (int(f.shape[1]*scale), int(f.shape[0]*scale)))
                return f
            
            # Initialize background
            if motion_state['stage'] == "inactive":
                motion_state['stage'] = "acquire_background"
                frame_resized = resize_frame(frame)
                gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0).astype("float32")
                motion_state['background'] = gray.copy()
                return
            
            # Process frame
            frame_resized = resize_frame(frame)
            height, width = frame_resized.shape[:2]
            max_area = height * width / 4
            
            frame_gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
            frame_blur = cv2.GaussianBlur(frame_gray, (blur_k, blur_k), 0)
            
            # Update background
            cv2.accumulateWeighted(frame_blur.astype("float32"), motion_state['background'], alpha)
            
            # Calibration phase
            if motion_state['stage'] == "acquire_background":
                motion_state['calibration'] += 1
                if motion_state['calibration'] > motion_state['duration']:
                    motion_state['stage'] = "active"
                    motion_state['calibration'] = 0
                    if verbose:
                        print("Motion detection active")
                return
            
            # Active detection
            if motion_state['stage'] == "active":
                background_uint8 = cv2.convertScaleAbs(motion_state['background'])
                diff = cv2.absdiff(background_uint8, frame_blur)
                _, motion_mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)
                
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel, iterations=1)
                motion_mask = cv2.dilate(motion_mask, kernel, iterations=2)
                
                contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for i, cnt in enumerate(contours):
                    area = cv2.contourArea(cnt)
                    if area < min_area or area > max_area:
                        continue
                    
                    x, y, w, h = cv2.boundingRect(cnt)
                    motion_id = f"motion_{i}"
                    
                    last_detection_data[motion_id] = {
                        'type': 'motion',
                        'box': (x, y, w, h),
                        'center': (x + w // 2, y + h // 2),
                        'offset': (((width // 2) - (x + w // 2)) / width,
                                  ((height // 2) - (y + h // 2)) / height),
                        'area': area
                    }
        
        except Exception as e:
            print(f"Error in motion detection: {e}")
    
    @staticmethod
    def detect_faces_simple(frame, face_cascade, last_detection_data, verbose=False):
        """Simple face detection using Haar Cascades"""
        try:
            height, width = frame.shape[:2]
            gray_image = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            faces = face_cascade.detectMultiScale(
                gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            
            for i, (x, y, w, h) in enumerate(faces):
                face_id = f"face_{i}"
                center_x = x + w // 2
                center_y = y + h // 2
                
                last_detection_data[face_id] = {
                    'type': 'face',
                    'box': (x, y, w, h),
                    'center': (center_x, center_y),
                    'offset': (((width // 2) - center_x) / width,
                              ((height // 2) - center_y) / height)
                }
                
                if verbose and i == 0:  # Only print first face
                    print(f"Face detected at ({center_x}, {center_y})")
        
        except Exception as e:
            print(f"Error in simple face detection: {e}")
    
    @staticmethod
    def detect_faces_advanced(frame, current_time, face_mesh, hands, face_cache, 
                             face_queue, emotion_queue, gesture_queue,
                             should_process_recognition, should_process_emotion, should_process_gesture,
                             hand_gesture, gesture_names, verbose=False):
        """
        Advanced face detection with MediaPipe, recognition, emotion, and gesture
        Returns updated hand_gesture value
        """
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Face Detection with MediaPipe
        try:
            face_results = face_mesh.process(rgb)
            
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
                    
                    face_id = face_cache.get_face_id(x_center, y_center, box)
                    face_crop = frame[y_min:y_max, x_min:x_max]
                    
                    if face_crop.size > 0:
                        # Face Recognition
                        if should_process_recognition:
                            if face_cache.needs_recognition(face_id) and not face_queue.full():
                                try:
                                    position_key = face_cache.get_position_key(x_center, y_center)
                                    face_queue.put_nowait((face_id, face_crop.copy(), position_key, current_time))
                                except:
                                    pass
                        
                        # Emotion Detection
                        if should_process_emotion:
                            face_data = face_cache.get_face_data(face_id)
                            if (current_time - face_data.get('last_emotion', 0) > 5.0 and
                                not emotion_queue.full()):
                                try:
                                    emotion_queue.put_nowait((face_id, face_crop.copy(), current_time))
                                except:
                                    pass
        
        except Exception as e:
            print(f"Error in face detection: {e}")
        
        # Gesture Detection
        if should_process_gesture:
            try:
                hand_results = hands.process(rgb)
                
                if hand_results.multi_hand_landmarks and hand_results.multi_handedness:
                    for hand_landmarks, handedness in zip(hand_results.multi_hand_landmarks,
                                                          hand_results.multi_handedness):
                        hand_type = handedness.classification[0].label
                        
                        if not gesture_queue.full():
                            try:
                                landmarks = hand_landmarks.landmark
                                gesture_queue.put_nowait((landmarks, hand_type, current_time))
                            except:
                                pass
                        
                        # Associate gesture to nearest face
                        wrist = hand_landmarks.landmark[0]
                        hand_x = wrist.x
                        hand_y = wrist.y
                        
                        closest_face_id = DetectionFunctions.associate_gesture_to_face(
                            hand_x, hand_y, w, h, face_cache
                        )
                        if closest_face_id is not None and hand_gesture != "Unknown":
                            face_cache.update_face(closest_face_id, 'gesture', hand_gesture)
            
            except Exception as e:
                print(f"Error in gesture detection: {e}")
        
        return hand_gesture
    
    @staticmethod
    def associate_gesture_to_face(hand_x, hand_y, w, h, face_cache):
        """Associate gesture to nearest face"""
        try:
            min_distance = float('inf')
            closest_face_id = None
            
            all_faces = face_cache.get_all_faces()
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