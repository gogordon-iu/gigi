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
from concurrent.futures import ThreadPoolExecutor

# === Configuration ===
DB_PATH = "emoface.pkl"
TOLERANCE = 0.6
MAX_QUEUE_SIZE = 5
NUM_WORKER_THREADS = 3  
# === Face Recognition DB ===
known_names = []
known_encodings = []

def load_db():
    global known_names, known_encodings
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'rb') as f:
            known_names, known_encodings = pickle.load(f)
        print(f"[INFO] Loaded {len(known_names)} known faces.")
    else:
        print("[INFO] No face database found. Starting fresh.")

def save_db():
    with open(DB_PATH, 'wb') as f:
        pickle.dump((known_names, known_encodings), f)
        print("[INFO] Face database saved.")

def add_known_face(name, image_path):
    try:
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        if encodings:
            known_names.append(name)
            known_encodings.append(encodings[0])
            print(f"[INFO] Added {name}")
            return True
        else:
            print(f"[WARN] No face found in {image_path}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to add {name}: {str(e)}")
        return False

def recognize_face(encoding):
    if not known_encodings:
        return "Unknown"
    matches = face_recognition.compare_faces(known_encodings, encoding, tolerance=TOLERANCE)
    if True in matches:
        face_distances = face_recognition.face_distance(known_encodings, encoding)
        best_match_idx = np.argmin(face_distances)
        if matches[best_match_idx]:
            return known_names[best_match_idx]
    return "Unknown"

# === Threaded Face Recognition Worker ===
def face_recognition_worker(face_queue, result_queue, stop_event):
    """Worker thread for face recognition processing"""
    while not stop_event.is_set():
        try:
            task = face_queue.get(timeout=0.1)
            if task is None:
                break
                
            face_id, face_crop, timestamp = task
            
            try:
                # Resize for faster processing
                small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
                face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
                face_encodings = face_recognition.face_encodings(face_crop_rgb)
                
                name = "Unknown"
                if face_encodings:
                    name = recognize_face(face_encodings[0])
                
                result_queue.put(('recognition', face_id, name, timestamp))
                
            except Exception as e:
                print(f"[ERROR] Face recognition failed: {str(e)}")
                result_queue.put(('recognition', face_id, "Unknown", timestamp))
            
            face_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"[ERROR] Face recognition worker error: {str(e)}")

# === Threaded Emotion Detection Worker ===
def emotion_detection_worker(emotion_queue, result_queue, stop_event):
    """Worker thread for emotion detection processing"""
    while not stop_event.is_set():
        try:
            task = emotion_queue.get(timeout=0.1)
            if task is None:
                break
                
            face_id, face_crop, timestamp = task
            
            try:
                # Resize for faster emotion detection
                emotion_face = cv2.resize(face_crop, (64, 64))
                emotion = detect_emotion(emotion_face)
                
                result_queue.put(('emotion', face_id, emotion, timestamp))
                
            except Exception as e:
                print(f"[ERROR] Emotion detection failed: {str(e)}")
                result_queue.put(('emotion', face_id, "Unknown", timestamp))
            
            emotion_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            print(f"[ERROR] Emotion detection worker error: {str(e)}")

# === Emotion Recognition with DeepFace ===
def detect_emotion(face_crop):
    try:
        # Convert to RGB (DeepFace expects RGB)
        face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        
        # Analyze face for emotion with optimized settings
        result = DeepFace.analyze(face_rgb, actions=['emotion'], enforce_detection=False, silent=True)
        
        # Return dominant emotion
        if isinstance(result, list):
            return result[0]['dominant_emotion']
        else:
            return result['dominant_emotion']
    except Exception as e:
        return "Unknown"

# === MediaPipe FaceMesh (Optimized) ===
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=3,
    refine_landmarks=False,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# === Thread-Safe Face Cache ===
class ThreadSafeFaceCache:
    def __init__(self):
        self.faces = {}
        self.next_id = 0
        self.lock = threading.Lock()
        
    def get_face_id(self, x_center, y_center, threshold=100):
        with self.lock:
            current_time = time.time()
            
            # Find existing face near this position
            for face_id, face_data in self.faces.items():
                if abs(face_data['x'] - x_center) < threshold and abs(face_data['y'] - y_center) < threshold:
                    face_data['x'] = x_center
                    face_data['y'] = y_center
                    face_data['last_seen'] = current_time
                    return face_id
            
            # Create new face
            face_id = self.next_id
            self.next_id += 1
            self.faces[face_id] = {
                'x': x_center, 
                'y': y_center, 
                'name': "Unknown", 
                'emotion': "Unknown",
                'last_recognition': 0,
                'last_emotion': 0,
                'last_seen': current_time
            }
            return face_id
    
    def update_face(self, face_id, field, value):
        with self.lock:
            if face_id in self.faces:
                self.faces[face_id][field] = value
                if field == 'name':
                    self.faces[face_id]['last_recognition'] = time.time()
                elif field == 'emotion':
                    self.faces[face_id]['last_emotion'] = time.time()
    
    def get_face_data(self, face_id):
        with self.lock:
            return self.faces.get(face_id, {}).copy()
    
    def cleanup_old_faces(self, timeout=3.0):
        with self.lock:
            current_time = time.time()
            to_remove = []
            for face_id, face_data in self.faces.items():
                if current_time - face_data['last_seen'] > timeout:
                    to_remove.append(face_id)
            
            for face_id in to_remove:
                del self.faces[face_id]

# === Main Program ===
def main():
    load_db()
    
    
    face_queue = Queue(maxsize=MAX_QUEUE_SIZE)
    emotion_queue = Queue(maxsize=MAX_QUEUE_SIZE)
    result_queue = Queue()
    stop_event = threading.Event()
    
    # Start worker threads
    threads = []
    
    # Face recognition workers
    for i in range(NUM_WORKER_THREADS):
        t = threading.Thread(target=face_recognition_worker, 
                           args=(face_queue, result_queue, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Emotion detection workers
    for i in range(NUM_WORKER_THREADS):
        t = threading.Thread(target=emotion_detection_worker, 
                           args=(emotion_queue, result_queue, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)
    
    # Initialize
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    emotion_counter = defaultdict(int)
    face_cache = ThreadSafeFaceCache()
    frame_count = 0
    
    # Performance tracking
    fps_start = time.time()
    fps_count = 0
    
    print("[INFO] Starting threaded face recognition...")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            fps_count += 1
            h, w = frame.shape[:2]
            current_time = time.time()
            
            # Process results from worker threads (non-blocking)
            while True:
                try:
                    result = result_queue.get_nowait()
                    result_type, face_id, value, timestamp = result
                    
                    if result_type == 'recognition':
                        face_cache.update_face(face_id, 'name', value)
                    elif result_type == 'emotion':
                        face_cache.update_face(face_id, 'emotion', value)
                        if value != "Unknown":
                            emotion_counter[value] += 1
                    
                except Empty:
                    break
            
            # Process MediaPipe on main thread (fast)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Get face coordinates
                    x_coords = [lm.x * w for lm in face_landmarks.landmark]
                    y_coords = [lm.y * h for lm in face_landmarks.landmark]
                    
                    x_min = max(int(min(x_coords)) - 30, 0)
                    x_max = min(int(max(x_coords)) + 30, w)
                    y_min = max(int(min(y_coords)) - 30, 0)
                    y_max = min(int(max(y_coords)) + 30, h)
                    
                    if x_max <= x_min or y_max <= y_min:
                        continue
                    
                    # Get face center and ID
                    x_center = (x_min + x_max) // 2
                    y_center = (y_min + y_max) // 2
                    face_id = face_cache.get_face_id(x_center, y_center)
                    face_data = face_cache.get_face_data(face_id)
                    
                    # Extract face crop
                    face_crop = frame[y_min:y_max, x_min:x_max]
                    
                    if face_crop.size > 0:
                        # Queue face recognition task (non-blocking)
                        if (current_time - face_data.get('last_recognition', 0) > 1.5 and
                            not face_queue.full()):
                            try:
                                face_queue.put_nowait((face_id, face_crop.copy(), current_time))
                            except:
                                pass  # Queue full, skip this frame
                        
                        # Queue emotion detection task (non-blocking)
                        if (current_time - face_data.get('last_emotion', 0) > 3.0 and
                            not emotion_queue.full()):
                            try:
                                emotion_queue.put_nowait((face_id, face_crop.copy(), current_time))
                            except:
                                pass  # Queue full, skip this frame
                    
                    # Draw results with current data
                    face_data = face_cache.get_face_data(face_id)  # Get updated data
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 2)
                    cv2.putText(frame, f"{face_data.get('name', 'Unknown')}: {face_data.get('emotion', 'Unknown')}", 
                               (x_min, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Cleanup old faces periodically
            if frame_count % 60 == 0:
                face_cache.cleanup_old_faces()
            
            # Display emotion stats
            if frame_count % 15 == 0:
                stats_y = 30
                cv2.putText(frame, "Emotion Stats:", (w - 200, stats_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                for i, (emo, count) in enumerate(sorted(emotion_counter.items(), key=lambda x: -x[1])[:5]):
                    cv2.putText(frame, f"{emo}: {count}", (w - 200, stats_y + 25 + i*25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display FPS
            if fps_count >= 30:
                fps = fps_count / (time.time() - fps_start)
                print(f"[INFO] FPS: {fps:.1f} | Face Queue: {face_queue.qsize()} | Emotion Queue: {emotion_queue.qsize()}")
                fps_count = 0
                fps_start = time.time()

            cv2.imshow("Face & Emotion Recognition (Threaded)", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord('s'):
                cv2.imwrite("capture.jpg", frame)
                print("[INFO] Saved frame as capture.jpg")
            elif key == ord('r'):
                emotion_counter.clear()
                print("[INFO] Reset emotion counters")

    except KeyboardInterrupt:
        print("\n[INFO] Stopping threads...")
    
    finally:
        # Clean shutdown
        stop_event.set()
        
        # Clear queues
        while not face_queue.empty():
            try:
                face_queue.get_nowait()
            except:
                break
                
        while not emotion_queue.empty():
            try:
                emotion_queue.get_nowait()
            except:
                break
        
        # Add None to wake up threads
        for _ in range(NUM_WORKER_THREADS * 2):
            try:
                face_queue.put(None, timeout=0.1)
                emotion_queue.put(None, timeout=0.1)
            except:
                pass
        
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=1.0)
        
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Cleanup complete")

if __name__ == "__main__":
    main()