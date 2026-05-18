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

DB_PATH = "../Resources/emoface_2.pkl"
TOLERANCE = 0.6
MAX_QUEUE_SIZE = 2
POSITION_MARGIN = 80
RECOGNITION_INTERVAL = 5.0
OVERLAP_THRESHOLD = 0.6

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
            except:
                pass
    
    def save_face_img_to_db(self, name, img):
        try:
            frame = cv2.imread(img)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mpi = MediaPipeInitializers()
            self.face_mesh = mpi.initialize_face_mesh()
            face_results = self.face_mesh.process(rgb)
            print(f'Face results: {face_results}')
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
                    
                    # x_center = (x_min + x_max) // 2
                    # y_center = (y_min + y_max) // 2
                    # box = (x_min, y_min, x_max, y_max)
                    
                    face_crop = frame[y_min:y_max, x_min:x_max]
                    small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
                    face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
                    face_encodings = face_recognition.face_encodings(face_crop_rgb)
                    self.save_face_to_db(name, face_encodings[0])
        except Exception as e:
            print(f"Error in save_face_img_to_db: {e}")
            pass

    def save_face_to_db(self, name, encoding):
        try:
            self.known_names.append(name)
            self.known_encodings.append(encoding)
            self.face_encodings_dict[name] = encoding
            
            with open(self.db_path, 'wb') as f:
                pickle.dump((self.known_names, self.known_encodings), f)
        except:
            pass
    
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
        except:
            pass
        
        return self.generate_face_id(), True
    
    def generate_face_id(self):
        return f"face_{random.randint(1000, 9999)}"

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
                    
                    # if is_new and name.startswith("face_"):
                    #     face_db.save_face_to_db(name, encoding)
                    
                    result_queue.put(('recognition', face_id, name, is_new, position_key, timestamp))
                else:
                    result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
            except:
                result_queue.put(('recognition', face_id, "Unknown", False, position_key, timestamp))
            
            face_queue.task_done()
        except Empty:
            continue
        except:
            pass


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
            except:
                result_queue.put(('emotion', face_id, "Unknown", timestamp))
            
            emotion_queue.task_done()
        except Empty:
            continue
        except:
            pass

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
            except:
                result_queue.put(('gesture', hand_type, "Unknown", timestamp))
            
            gesture_queue.task_done()
        except Empty:
            continue
        except:
            pass


class GestureRecognizer:
    @staticmethod
    def recognize_gesture_fast(landmarks):
        try:
            finger_pattern = GestureRecognizer.get_finger_states_fast(landmarks)
            
            # Count extended fingers
            extended_count = sum(finger_pattern)
            
            # Specific patterns
            if finger_pattern == (True, False, False, False, False):
                return GestureRecognizer.check_thumb_direction(landmarks)
            elif finger_pattern == (False, False, False, False, False):
                return 5  # Fist
            elif extended_count == 5:
                return 6  # Open hand
            elif finger_pattern == (False, True, False, False, False):
                return 7  # Pointing
            elif finger_pattern == (True, True, False, False, False):
                return 6  # Peace/Victory (treat as open hand)
            elif extended_count >= 3:
                return 6  # Open hand (lenient)
            elif extended_count == 0:
                return 5  # Fist (lenient)
            else:
                return 0
        except:
            return 0

    @staticmethod
    def get_finger_states_fast(landmarks):
        fingers = []
        
        # Thumb - check if extended from palm
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]
        wrist = landmarks[0]
        
        # Distance from wrist
        thumb_dist = ((thumb_tip.x - wrist.x)**2 + (thumb_tip.y - wrist.y)**2)**0.5
        mcp_dist = ((thumb_mcp.x - wrist.x)**2 + (thumb_mcp.y - wrist.y)**2)**0.5
        fingers.append(thumb_dist > mcp_dist * 1.3)
        
        # Other fingers - check if tip is above PIP joint
        finger_tip_ids = [8, 12, 16, 20]
        finger_pip_ids = [6, 10, 14, 18]
        
        for i in range(4):
            tip = landmarks[finger_tip_ids[i]]
            pip = landmarks[finger_pip_ids[i]]
            wrist = landmarks[0]
            
            # Distance-based check (more robust)
            tip_dist = ((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2)**0.5
            pip_dist = ((pip.x - wrist.x)**2 + (pip.y - wrist.y)**2)**0.5
            
            fingers.append(tip_dist > pip_dist * 1.1)
        
        return tuple(fingers)

    @staticmethod
    def check_thumb_direction(landmarks):
        thumb_tip_y = landmarks[4].y
        wrist_y = landmarks[0].y
        return 1 if thumb_tip_y < wrist_y else 2

class ImprovedFaceCache:
    def __init__(self):
        self.faces = {}
        self.position_to_face = {}
        self.next_id = 1
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
                'recognition_attempted': False,
                'is_new': True
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
                self.faces[face_id]['is_new'] = False
                
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
            
            # Prioritize new faces - always recognize immediately
            if face_data.get('is_new', False):
                return True
            
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

class VisionHelpers:
    @staticmethod
    def draw_face_info(frame, x_min, y_min, x_max, y_max, face_data):
        try:
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 2)
            
            x_center = face_data.get('x', 0)
            y_center = face_data.get('y', 0)
            
            crosshair_size = 10
            cv2.line(frame, (x_center - crosshair_size, y_center), 
                    (x_center + crosshair_size, y_center), (0, 255, 255), 2)
            cv2.line(frame, (x_center, y_center - crosshair_size), 
                    (x_center, y_center + crosshair_size), (0, 255, 255), 2)
            cv2.circle(frame, (x_center, y_center), 3, (0, 255, 255), -1)
            
            name = face_data.get('name', 'Recognizing...')
            emotion = face_data.get('emotion', 'Unknown')
            gesture = face_data.get('gesture', 'Unknown')
            
            label = f"{name}"
            if emotion != 'Unknown':
                label += f" | {emotion}"
            if gesture != 'Unknown':
                label += f" | {gesture}"
            
            coord_label = f"({x_center}, {y_center})"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            cv2.rectangle(frame, (x_min, y_min - text_height - 10), 
                         (x_min + text_width, y_min), (0, 255, 255), -1)
            cv2.putText(frame, label, (x_min, y_min - 5), 
                       font, font_scale, (0, 0, 0), thickness)
            
            (coord_width, coord_height), coord_baseline = cv2.getTextSize(coord_label, font, font_scale, thickness)
            cv2.rectangle(frame, (x_min, y_max), 
                         (x_min + coord_width, y_max + coord_height + 10), (0, 255, 255), -1)
            cv2.putText(frame, coord_label, (x_min, y_max + coord_height + 5), 
                       font, font_scale, (0, 0, 0), thickness)
        except:
            pass
    
    @staticmethod
    def associate_gesture_to_face(hand_x, hand_y, w, h, all_faces):
        try:
            min_distance = float('inf')
            closest_face_id = None
            
            for face_id, face_data in all_faces.items():
                face_x = face_data['x'] / w
                face_y = face_data['y'] / h
                
                distance = ((hand_x - face_x)**2 + (hand_y - face_y)**2)**0.5
                
                if distance < min_distance and distance < 0.3:
                    min_distance = distance
                    closest_face_id = face_id
            
            return closest_face_id
        except:
            return None
    
    @staticmethod
    def update_data_structure(face_cache, last_data, timestamped_data):
        timestamp = time.strftime("%H:%M:%S")
        current_data = {}
        all_faces = face_cache.get_all_faces()
        
        for face_id, face_data in all_faces.items():
            face_id_str = str(face_id).zfill(4)
            
            if face_id_str not in last_data:
                last_data[face_id_str] = {}
            
            current_face_data = {}
            
            name = face_data.get('name', 'Unknown')
            if name not in ['Recognizing...', 'Unknown']:
                current_face_data['name'] = name
                last_data[face_id_str]['name'] = name
            elif 'name' in last_data[face_id_str]:
                current_face_data['name'] = last_data[face_id_str]['name']
            else:
                current_face_data['name'] = name
            
            emotion = face_data.get('emotion', 'Unknown')
            if emotion != 'Unknown':
                current_face_data['emotion'] = emotion
                last_data[face_id_str]['emotion'] = emotion
            elif 'emotion' in last_data[face_id_str]:
                current_face_data['emotion'] = last_data[face_id_str]['emotion']
            else:
                current_face_data['emotion'] = emotion
            
            gesture = face_data.get('gesture', 'Unknown')
            if gesture != 'Unknown':
                current_face_data['gesture'] = gesture
                last_data[face_id_str]['gesture'] = gesture
            elif 'gesture' in last_data[face_id_str]:
                current_face_data['gesture'] = last_data[face_id_str]['gesture']
            else:
                current_face_data['gesture'] = gesture
            
            current_face_data['center_x'] = face_data.get('x', 0)
            current_face_data['center_y'] = face_data.get('y', 0)
            last_data[face_id_str]['center_x'] = current_face_data['center_x']
            last_data[face_id_str]['center_y'] = current_face_data['center_y']
            
            current_data[face_id_str] = current_face_data
        
        if current_data:
            timestamped_data[timestamp] = current_data
    
    @staticmethod
    def look_for_worker(what, timeout, result_container, stop_event, get_data_func):
        start_time = time.time()
        while not stop_event.is_set():
            if time.time() - start_time > timeout:
                result_container['found'] = False
                result_container['data'] = None
                result_container['done'] = True
                return
            
            data = get_data_func()
            
            for face_id, face_info in data.items():
                match = True
                
                if 'name' in what and face_info.get('name', 'Unknown') != what['name']:
                    match = False
                if 'emotion' in what and face_info.get('emotion', 'Unknown') != what['emotion']:
                    match = False
                if 'gesture' in what and face_info.get('gesture', 'Unknown') != what['gesture']:
                    match = False
                
                if match:
                    result_container['found'] = True
                    result_container['data'] = {face_id: face_info}
                    result_container['done'] = True
                    return
            
            time.sleep(0.1)
        
        result_container['found'] = False
        result_container['data'] = None
        result_container['done'] = True

if __name__ == "__main__":
    fd = FaceDatabase()
    fd.save_face_img_to_db("Stephanie", "../temp/StephanieKim.jpg.webp")