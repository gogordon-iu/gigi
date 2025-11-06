import cv2
import time
import threading
from queue import Queue, Empty
from datetime import datetime
from collections import defaultdict
import vision_helper as vh
import time
from datetime import datetime, timedelta

class Vision:
    def __init__(self, port=None, verbose=False):
        """
        Initialize Vision System with multi-detection capabilities
        
        Args:
            port: Camera port (None for auto-detect)
            verbose: Enable verbose logging
        """
        print("Initializing vision system...")
        self.verbose = verbose
        
        # Camera
        self.cap = self.open_camera(port)
        
        # Detection components (lazy initialization)
        self.face_db = vh.FaceDatabase()
        self.emotion_detector = vh.EmotionDetector()
        self.face_cache = vh.ImprovedFaceCache()
        
        # MediaPipe components (initialized on first use)
        self.face_mesh = None
        self.hands = None
        
        # Haar Cascade for simple face detection
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # FPS Configuration for each detection type
        self.fps_config = {
            'qr': 5,              # QR codes - 5 fps
            'face_detection': 15,  # Face detection - 15 fps
            'face_recognition': 1, # Face recognition - 1 fps (expensive)
            'emotion': 2,          # Emotion detection - 2 fps (expensive)
            'gesture': 10,         # Gesture recognition - 10 fps
            'motion': 5            # Motion detection - 5 fps
        }
        
        # Last processing time for FPS control
        self.last_process_time = {key: 0 for key in self.fps_config.keys()}
        
        # Gesture configuration
        self.gesture_names = {
            0: "Unknown", 1: "Thumbs Up", 2: "Thumbs Down",
            5: "Rock/Fist", 6: "Open Hand", 7: "Pointing"
        }
        self.hand_gesture = "Unknown"
        
        # Data structure: timestamp-based with nested dictionaries
        self.detection_history = {}
        self.last_frame = None
        self.last_detection_data = {}
        
        # Motion detection state
        self.motion_state = {
            'stage': 'inactive',
            'calibration': 0,
            'duration': 10,
            'background': None
        }
        
        # Threading components
        self.camera_thread = None
        self.stop_event = threading.Event()
        
        # Worker queues
        self.face_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.emotion_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.gesture_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.result_queue = Queue()
        
        # Track active workers
        self.active_workers = {
            'face_recognition': False,
            'emotion': False,
            'gesture': False
        }
        self.worker_threads = []
        
        # Lock for thread-safe data access
        self.data_lock = threading.Lock()
        
        print("Vision system initialized successfully!")
    
    def open_camera(self, port):
        """Open camera on specified or auto-detected port"""
        if port is None:
            ports = range(10)
        else:
            ports = [port]
        
        for p in ports:
            if self.verbose:
                print(f"Checking camera port {p}...")
            cap = cv2.VideoCapture(p)
            if cap.isOpened():
                print(f"Camera opened successfully on port {p}")
                return cap
        
        print("ERROR: Unable to open camera!")
        return None
    
    def should_process(self, detection_type, current_time):
        """
        Check if we should process this detection type based on FPS config
        
        Args:
            detection_type: Type of detection
            current_time: Current timestamp
        
        Returns:
            bool: True if enough time has passed since last processing
        """
        if detection_type not in self.fps_config:
            return True
        
        fps = self.fps_config[detection_type]
        if fps == 0:
            return False
        
        interval = 1.0 / fps
        time_since_last = current_time - self.last_process_time[detection_type]
        
        if time_since_last >= interval:
            self.last_process_time[detection_type] = current_time
            return True
        
        return False
    
    def start_worker_if_needed(self, worker_type):
        """Start specific worker thread if not already running"""
        if self.active_workers[worker_type]:
            return
        
        if worker_type == 'face_recognition':
            t = threading.Thread(
                target=vh.face_recognition_worker,
                args=(self.face_queue, self.result_queue, self.stop_event, self.face_db),
                name="FaceRecognition",
                daemon=True
            )
            t.start()
            self.worker_threads.append(t)
            self.active_workers['face_recognition'] = True
            if self.verbose:
                print("Started face recognition worker")
        
        elif worker_type == 'emotion':
            t = threading.Thread(
                target=vh.emotion_detection_worker,
                args=(self.emotion_queue, self.result_queue, self.stop_event, self.emotion_detector),
                name="EmotionDetection",
                daemon=True
            )
            t.start()
            self.worker_threads.append(t)
            self.active_workers['emotion'] = True
            if self.verbose:
                print("Started emotion detection worker")
        
        elif worker_type == 'gesture':
            t = threading.Thread(
                target=vh.gesture_recognition_worker,
                args=(self.gesture_queue, self.result_queue, self.stop_event, self.gesture_names),
                name="GestureRecognition",
                daemon=True
            )
            t.start()
            self.worker_threads.append(t)
            self.active_workers['gesture'] = True
            if self.verbose:
                print("Started gesture recognition worker")
    
    def initialize_face_detection(self):
        """Initialize MediaPipe face detection if not already initialized"""
        if self.face_mesh is None:
            self.face_mesh = vh.MediaPipeInitializers.initialize_face_mesh()
            if self.verbose:
                print("Initialized MediaPipe Face Mesh")
    
    def initialize_gesture_detection(self):
        """Initialize MediaPipe gesture detection if not already initialized"""
        if self.hands is None:
            self.hands = vh.MediaPipeInitializers.initialize_hands()
            if self.verbose:
                print("Initialized MediaPipe Hands")
    
    def process_results(self):
        """Process results from worker threads"""
        while True:
            try:
                result = self.result_queue.get_nowait()
                
                if result[0] == 'recognition':
                    _, face_id, name, is_new, position_key, timestamp = result
                    self.face_cache.update_face_name(face_id, name, position_key)
                    if self.verbose:
                        print(f"Face recognized: {name} (ID: {face_id})")
                
                elif result[0] == 'emotion':
                    _, face_id, emotion, timestamp = result
                    self.face_cache.update_face(face_id, 'emotion', emotion)
                    if self.verbose:
                        print(f"Emotion detected: {emotion} (ID: {face_id})")
                
                elif result[0] == 'gesture':
                    _, hand_type, gesture_name, timestamp = result
                    self.hand_gesture = gesture_name
                    if self.verbose:
                        print(f"Gesture detected: {gesture_name} ({hand_type})")
            
            except Empty:
                break
            except Exception as e:
                print(f"Error processing results: {e}")
                break
    
    def update_detection_history(self, current_time):
        """
        Update detection history with timestamp-based structure
        Format: {'timestamp': {'face_id': {'feature': value}}}
        """
        with self.data_lock:
            timestamp = datetime.fromtimestamp(current_time).strftime('%H:%M:%S.%f')[:-3]
            
            # Create new timestamp entry
            self.detection_history[timestamp] = {}
            
            # Add all faces from cache
            all_faces = self.face_cache.get_all_faces()
            for face_id, face_data in all_faces.items():
                face_id_str = str(face_id).zfill(4)
                
                self.detection_history[timestamp][face_id_str] = {
                    'name': face_data.get('name', 'Recognizing...'),
                    'emotion': face_data.get('emotion', 'Unknown'),
                    'gesture': face_data.get('gesture', 'Unknown'),
                    'center_x': face_data.get('x', 0),
                    'center_y': face_data.get('y', 0),
                    'box': face_data.get('box', (0, 0, 0, 0))
                }
                
                # Update last known values
                self.last_detection_data[face_id_str] = self.detection_history[timestamp][face_id_str].copy()
            
            # If no new detections, copy from last known data
            if not self.detection_history[timestamp] and self.last_detection_data:
                for face_id, data in self.last_detection_data.items():
                    if isinstance(data, dict) and data.get('type') != 'qr' and data.get('type') != 'motion':
                        self.detection_history[timestamp][face_id] = data.copy()
            
            # Limit history size (keep last 100 entries)
            if len(self.detection_history) > 100:
                oldest_key = min(self.detection_history.keys())
                del self.detection_history[oldest_key]
    
    def camera_loop(self, detection_types=None):
        """
        Main camera processing loop running in separate thread
        
        Args:
            detection_types: List of detection types to enable
        """
        if detection_types is None:
            detection_types = ['face_advanced']
        
        print(f"Camera thread started with detections: {detection_types}")
        
        frame_count = 0
        
        while not self.stop_event.is_set():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to capture frame")
                    time.sleep(0.1)
                    continue
                
                frame_count += 1
                current_time = time.time()
                
                # Store last frame
                self.last_frame = frame.copy()
                
                # Process results from worker threads
                self.process_results()
                
                # QR Code Detection
                if 'qr' in detection_types and self.should_process('qr', current_time):
                    vh.DetectionFunctions.detect_qr(frame, self.last_detection_data, self.verbose)
                
                # Simple Face Detection (Haar Cascades)
                if 'face_simple' in detection_types and self.should_process('face_detection', current_time):
                    vh.DetectionFunctions.detect_faces_simple(
                        frame, self.face_cascade, self.last_detection_data, self.verbose
                    )
                
                # Advanced Face Detection (MediaPipe + Recognition + Emotion + Gesture)
                if 'face_advanced' in detection_types:
                    # Initialize if needed
                    if self.should_process('face_detection', current_time):
                        self.initialize_face_detection()
                    
                    if self.should_process('gesture', current_time):
                        self.initialize_gesture_detection()
                    
                    # Start workers if needed
                    if self.should_process('face_recognition', current_time):
                        self.start_worker_if_needed('face_recognition')
                    
                    if self.should_process('emotion', current_time):
                        self.start_worker_if_needed('emotion')
                    
                    if self.should_process('gesture', current_time):
                        self.start_worker_if_needed('gesture')
                    
                    # Run detection
                    should_face_det = self.should_process('face_detection', current_time)
                    should_face_rec = self.should_process('face_recognition', current_time)
                    should_emotion = self.should_process('emotion', current_time)
                    should_gesture = self.should_process('gesture', current_time)
                    
                    if should_face_det or should_face_rec or should_emotion or should_gesture:
                        self.hand_gesture = vh.DetectionFunctions.detect_faces_advanced(
                            frame, current_time, self.face_mesh, self.hands, self.face_cache,
                            self.face_queue, self.emotion_queue, self.gesture_queue,
                            should_face_rec, should_emotion, should_gesture,
                            self.hand_gesture, self.gesture_names, self.verbose
                        )
                
                # Motion Detection
                if 'motion' in detection_types and self.should_process('motion', current_time):
                    vh.DetectionFunctions.detect_motion(
                        frame, self.motion_state, self.last_detection_data, self.verbose
                    )
                
                # Update detection history
                self.update_detection_history(current_time)
                
                # Periodic cleanup
                if frame_count % 300 == 0:
                    self.face_cache.cleanup_old_faces()
                
                # Small sleep to prevent CPU overload
                time.sleep(0.001)
            
            except Exception as e:
                print(f"Error in camera loop: {e}")
                time.sleep(0.1)
        
        print("Camera thread stopped")
    
    def start_camera(self, detection_types=None):
        """
        Start camera processing in separate thread
        
        Args:
            detection_types: List of detection types to enable
        """
        if self.camera_thread and self.camera_thread.is_alive():
            print("Camera thread already running")
            return
        
        if self.cap is None or not self.cap.isOpened():
            print("ERROR: Camera not available")
            return
        
        self.stop_event.clear()
        self.camera_thread = threading.Thread(
            target=self.camera_loop,
            args=(detection_types,),
            name="CameraThread",
            daemon=True
        )
        self.camera_thread.start()
        print("Camera thread started successfully")
        
        # Give it a moment to initialize
        time.sleep(1)
    
    def stop_camera(self):
        """Stop camera processing thread"""
        if not self.camera_thread or not self.camera_thread.is_alive():
            print("Camera thread not running")
            return
        
        print("Stopping camera thread...")
        self.stop_event.set()
        
        if self.camera_thread:
            self.camera_thread.join(timeout=2.0)
            self.camera_thread = None
        
        print("Camera thread stopped")
    
    def get_detection_history(self, last_n=10):
        """
        Get detection history for last N timestamps
        
        Args:
            last_n: Number of most recent timestamps to return
        
        Returns:
            Dictionary with last N timestamps
        """
        with self.data_lock:
            all_timestamps = sorted(self.detection_history.keys())
            recent_timestamps = all_timestamps[-last_n:] if len(all_timestamps) > last_n else all_timestamps
            
            return {ts: self.detection_history[ts] for ts in recent_timestamps}
    
    def get_latest_detection(self):
        """Get the most recent detection data"""
        with self.data_lock:
            if not self.detection_history:
                return None
            
            latest_timestamp = max(self.detection_history.keys())
            return {latest_timestamp: self.detection_history[latest_timestamp]}
    
    def get_last_frame(self):
        """Get the last captured frame"""
        return self.last_frame.copy() if self.last_frame is not None else None
    
    def print_detection_data(self, last_n=5):
        """Print detection data in readable format"""
        history = self.get_detection_history(last_n)
        
        print("\n" + "="*80)
        print(f"DETECTION HISTORY (Last {last_n} timestamps):")
        print("="*80)
        
        for timestamp, faces in history.items():
            print(f"\n[{timestamp}]")
            if faces:
                for face_id, data in faces.items():
                    print(f"  Face {face_id}:")
                    for key, value in data.items():
                        if key != 'box':
                            print(f"    {key}: {value}")
            else:
                print("  No faces detected")
        
        print("="*80 + "\n")
    
    def set_fps(self, detection_type, fps):
        """
        Set FPS for a specific detection type
        
        Args:
            detection_type: Type of detection
            fps: Frames per second (0 to disable)
        """
        if detection_type in self.fps_config:
            self.fps_config[detection_type] = fps
            print(f"Set {detection_type} FPS to {fps}")
        else:
            print(f"Unknown detection type: {detection_type}")
    
    def get_fps_config(self):
        """Get current FPS configuration"""
        return self.fps_config.copy()
    
    def cleanup(self):
        """Cleanup all resources"""
        print("Cleaning up vision system...")
        
        # Stop camera thread
        self.stop_camera()
        
        # Stop worker threads
        self.stop_event.set()
        
        # Clear queues
        for q in [self.face_queue, self.emotion_queue, self.gesture_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except:
                    break
        
        # Send poison pills
        for _ in range(len(self.worker_threads)):
            try:
                self.face_queue.put(None, timeout=0.1)
                self.emotion_queue.put(None, timeout=0.1)
                self.gesture_queue.put(None, timeout=0.1)
            except:
                pass
        
        # Join worker threads
        for thread in self.worker_threads:
            thread.join(timeout=1.0)
        
        # Release camera
        if self.cap:
            self.cap.release()
        
        cv2.destroyAllWindows()
        print("Cleanup complete")

"""
look_for() function for Vision class
Probes the data structure with flexible query parameters
"""

import time
from datetime import datetime, timedelta

def look_for(self, what=None, timeout=10, interval=0.1, mode='any'):
    """
    Search for specific data in the detection history
    
    Args:
        what: Dictionary with search criteria. Can include:
            - 'face_id': str or list - Specific face ID(s)
            - 'name': str or list - Face name(s)
            - 'emotion': str or list - Emotion(s)
            - 'gesture': str or list - Gesture(s)
            - 'qr_data': str or list - QR code data
            - 'time_after': str - Search after this time (HH:MM:SS)
            - 'time_before': str - Search before this time (HH:MM:SS)
            - 'min_faces': int - Minimum number of faces
            - 'max_faces': int - Maximum number of faces
            - 'center_x_min': int - Minimum X coordinate
            - 'center_x_max': int - Maximum X coordinate
            - 'center_y_min': int - Minimum Y coordinate
            - 'center_y_max': int - Maximum Y coordinate
            - 'has_motion': bool - Motion detected
            - 'has_qr': bool - QR code detected
        
        timeout: Maximum time to wait in seconds (-1 for no timeout)
        interval: How often to check in seconds
        mode: 'any' (match any condition) or 'all' (match all conditions)
    
    Returns:
        Dictionary with matching results:
        {
            'found': bool,                    # Whether anything was found
            'matches': [                      # List of matching entries
                {
                    'timestamp': str,
                    'data': {...}             # Full data at that timestamp
                },
                ...
            ],
            'search_time': float,             # How long the search took
            'query': dict                     # The query that was used
        }
    
    Examples:
        # Look for a specific person
        result = vision.look_for({'name': 'Goren'})
        
        # Look for happy faces
        result = vision.look_for({'emotion': 'happy'})
        
        # Look for thumbs up gesture
        result = vision.look_for({'gesture': 'Thumbs Up'})
        
        # Look for specific QR code
        result = vision.look_for({'qr_data': 'ABC123'})
        
        # Look for at least 2 faces
        result = vision.look_for({'min_faces': 2})
        
        # Look for multiple conditions (any match)
        result = vision.look_for({
            'name': ['Goren', 'Gowtham'],
            'emotion': 'happy'
        }, mode='any')
        
        # Look for all conditions (all must match)
        result = vision.look_for({
            'name': 'Goren',
            'emotion': 'happy',
            'gesture': 'Thumbs Up'
        }, mode='all')
        
        # Look for data in time range
        result = vision.look_for({
            'time_after': '10:30:00',
            'time_before': '10:35:00'
        })
        
        # Look for face in specific area
        result = vision.look_for({
            'center_x_min': 200,
            'center_x_max': 400,
            'center_y_min': 150,
            'center_y_max': 350
        })
    """
    if what is None:
        what = {}
    
    start_time = time.time()
    matches = []
    
    # Helper function to check if value matches criteria
    def matches_criteria(value, criteria):
        if isinstance(criteria, list):
            return value in criteria
        else:
            return value == criteria
    
    # Helper function to parse time string to comparable format
    def parse_time(time_str):
        try:
            # Handle HH:MM:SS or HH:MM:SS.mmm format
            if '.' in time_str:
                return datetime.strptime(time_str, '%H:%M:%S.%f').time()
            else:
                return datetime.strptime(time_str, '%H:%M:%S').time()
        except:
            return None
    
    # Helper function to check if timestamp matches time criteria
    def matches_time_range(timestamp_str, time_after=None, time_before=None):
        timestamp_time = parse_time(timestamp_str)
        if timestamp_time is None:
            return False
        
        if time_after:
            after_time = parse_time(time_after)
            if after_time and timestamp_time < after_time:
                return False
        
        if time_before:
            before_time = parse_time(time_before)
            if before_time and timestamp_time > before_time:
                return False
        
        return True
    
    # Main search function
    def search_data():
        with self.data_lock:
            current_matches = []
            
            # Search detection history
            for timestamp, faces_data in self.detection_history.items():
                # Check time range first
                if 'time_after' in what or 'time_before' in what:
                    if not matches_time_range(timestamp, 
                                             what.get('time_after'), 
                                             what.get('time_before')):
                        continue
                
                # Check face count criteria
                num_faces = len(faces_data)
                if 'min_faces' in what and num_faces < what['min_faces']:
                    continue
                if 'max_faces' in what and num_faces > what['max_faces']:
                    continue
                
                # Check each face in this timestamp
                for face_id, face_data in faces_data.items():
                    conditions_met = []
                    
                    # Check face_id
                    if 'face_id' in what:
                        conditions_met.append(matches_criteria(face_id, what['face_id']))
                    
                    # Check name
                    if 'name' in what:
                        conditions_met.append(matches_criteria(face_data.get('name'), what['name']))
                    
                    # Check emotion
                    if 'emotion' in what:
                        conditions_met.append(matches_criteria(face_data.get('emotion'), what['emotion']))
                    
                    # Check gesture
                    if 'gesture' in what:
                        conditions_met.append(matches_criteria(face_data.get('gesture'), what['gesture']))
                    
                    # Check position
                    if 'center_x_min' in what:
                        conditions_met.append(face_data.get('center_x', 0) >= what['center_x_min'])
                    if 'center_x_max' in what:
                        conditions_met.append(face_data.get('center_x', 0) <= what['center_x_max'])
                    if 'center_y_min' in what:
                        conditions_met.append(face_data.get('center_y', 0) >= what['center_y_min'])
                    if 'center_y_max' in what:
                        conditions_met.append(face_data.get('center_y', 0) <= what['center_y_max'])
                    
                    # Check if conditions are met based on mode
                    if conditions_met:
                        if mode == 'all' and all(conditions_met):
                            current_matches.append({
                                'timestamp': timestamp,
                                'face_id': face_id,
                                'data': face_data.copy()
                            })
                        elif mode == 'any' and any(conditions_met):
                            current_matches.append({
                                'timestamp': timestamp,
                                'face_id': face_id,
                                'data': face_data.copy()
                            })
            
            # Check QR codes
            if 'qr_data' in what or 'has_qr' in what:
                for key, data in self.last_detection_data.items():
                    if key.startswith('qr_'):
                        if 'qr_data' in what:
                            if matches_criteria(data.get('data'), what['qr_data']):
                                current_matches.append({
                                    'timestamp': 'current',
                                    'type': 'qr',
                                    'data': data.copy()
                                })
                        elif 'has_qr' in what and what['has_qr']:
                            current_matches.append({
                                'timestamp': 'current',
                                'type': 'qr',
                                'data': data.copy()
                            })
            
            # Check motion
            if 'has_motion' in what and what['has_motion']:
                for key, data in self.last_detection_data.items():
                    if key.startswith('motion_'):
                        current_matches.append({
                            'timestamp': 'current',
                            'type': 'motion',
                            'data': data.copy()
                        })
            
            return current_matches
    
    # Wait loop
    if timeout == -1:
        # No timeout - search once
        matches = search_data()
    else:
        # Wait until timeout or found
        end_time = start_time + timeout
        while time.time() < end_time:
            matches = search_data()
            if matches:
                break
            time.sleep(interval)
    
    search_time = time.time() - start_time
    
    result = {
        'found': len(matches) > 0,
        'matches': matches,
        'count': len(matches),
        'search_time': round(search_time, 3),
        'query': what.copy()
    }
    
    if self.verbose:
        if result['found']:
            print(f"Found {result['count']} match(es) in {result['search_time']}s")
        else:
            print(f"No matches found in {result['search_time']}s")
    
    return result


# Additional helper method for simpler queries
def find_face(self, name=None, emotion=None, gesture=None, timeout=5):
    """
    Simplified face search
    
    Args:
        name: Face name to search for
        emotion: Emotion to search for
        gesture: Gesture to search for
        timeout: Maximum wait time
    
    Returns:
        First matching face data or None
    """
    criteria = {}
    if name:
        criteria['name'] = name
    if emotion:
        criteria['emotion'] = emotion
    if gesture:
        criteria['gesture'] = gesture
    
    result = self.look_for(criteria, timeout=timeout, mode='all')
    
    if result['found']:
        return result['matches'][0]
    return None


def wait_for_qr(self, qr_data=None, timeout=10):
    """
    Wait for a QR code to be detected
    
    Args:
        qr_data: Specific QR data to wait for (None for any QR)
        timeout: Maximum wait time
    
    Returns:
        QR code data or None
    """
    if qr_data:
        result = self.look_for({'qr_data': qr_data}, timeout=timeout)
    else:
        result = self.look_for({'has_qr': True}, timeout=timeout)
    
    if result['found']:
        return result['matches'][0]
    return None


def wait_for_gesture(self, gesture, timeout=10):
    """
    Wait for a specific gesture to be detected
    
    Args:
        gesture: Gesture name to wait for
        timeout: Maximum wait time
    
    Returns:
        Face with gesture or None
    """
    result = self.look_for({'gesture': gesture}, timeout=timeout)
    
    if result['found']:
        return result['matches'][0]
    return None


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
# Example 1: Look for a specific person
vision = Vision()
vision.start_camera(detection_types=['face_advanced'])

result = vision.look_for({'name': 'Goren'}, timeout=10)
if result['found']:
    print(f"Found Goren at {result['matches'][0]['timestamp']}")


# Example 2: Look for happy faces
result = vision.look_for({'emotion': 'happy'}, timeout=5)
print(f"Found {result['count']} happy faces")
for match in result['matches']:
    print(f"  - {match['data']['name']} at {match['timestamp']}")


# Example 3: Look for thumbs up gesture
result = vision.look_for({'gesture': 'Thumbs Up'}, timeout=10)
if result['found']:
    print("Someone gave a thumbs up!")


# Example 4: Look for QR code
result = vision.look_for({'qr_data': 'ABC123'}, timeout=15)
if result['found']:
    print(f"Found QR code: {result['matches'][0]['data']['data']}")


# Example 5: Look for multiple faces
result = vision.look_for({'min_faces': 2}, timeout=10)
if result['found']:
    print(f"Found {result['count']} timestamps with 2+ faces")


# Example 6: Complex query - all conditions must match
result = vision.look_for({
    'name': 'Goren',
    'emotion': 'happy',
    'gesture': 'Thumbs Up'
}, mode='all', timeout=15)

if result['found']:
    print("Found Goren who is happy and giving thumbs up!")


# Example 7: Look for any of multiple conditions
result = vision.look_for({
    'name': ['Goren', 'Gowtham', 'Alice'],
    'emotion': ['happy', 'surprised']
}, mode='any', timeout=10)


# Example 8: Time-based search
result = vision.look_for({
    'time_after': '10:30:00',
    'time_before': '10:35:00',
    'emotion': 'happy'
})


# Example 9: Position-based search
result = vision.look_for({
    'center_x_min': 200,
    'center_x_max': 400,
    'center_y_min': 150,
    'center_y_max': 350
}, timeout=5)


# Example 10: Using simplified helper methods
face = vision.find_face(name='Goren', emotion='happy', timeout=5)
if face:
    print(f"Found Goren: {face['data']}")

qr = vision.wait_for_qr(qr_data='ABC123', timeout=10)
if qr:
    print(f"QR code detected: {qr['data']}")

gesture_face = vision.wait_for_gesture('Thumbs Up', timeout=10)
if gesture_face:
    print(f"{gesture_face['data']['name']} gave thumbs up!")


# Example 11: Continuous monitoring
while True:
    result = vision.look_for({'emotion': 'angry'}, timeout=1)
    if result['found']:
        print("Warning: Angry face detected!")
        break
    time.sleep(0.1)


# Example 12: Wait for specific sequence
# Wait for person to appear
result1 = vision.look_for({'name': 'Goren'}, timeout=10)
if result1['found']:
    # Wait for them to smile
    result2 = vision.look_for({'name': 'Goren', 'emotion': 'happy'}, timeout=5)
    if result2['found']:
        # Wait for thumbs up
        result3 = vision.look_for({'name': 'Goren', 'gesture': 'Thumbs Up'}, timeout=5)
        if result3['found']:
            print("Complete sequence detected!")
"""

# Example usage
if __name__ == "__main__":
    # Create vision system
    vision = Vision(verbose=True)
    
    # Configure FPS for each detection type
    vision.set_fps('face_detection', 15)
    vision.set_fps('face_recognition', 1)
    vision.set_fps('emotion', 2)
    vision.set_fps('gesture', 10)
    vision.set_fps('qr', 5)
    
    print("\nFPS Configuration:")
    for detection, fps in vision.get_fps_config().items():
        print(f"  {detection}: {fps} fps")
    
    try:
        # Start camera with all detections
        vision.start_camera(detection_types=['face_advanced', 'qr', 'motion'])
        
        # Run for 30 seconds
        print("\nRunning for 30 seconds...")
        for i in range(6):
            time.sleep(5)
            print(f"\n--- After {(i+1)*5} seconds ---")
            vision.print_detection_data(last_n=3)
        
        # Get latest detection
        latest = vision.get_latest_detection()
        if latest:
            print("\nLatest Detection:")
            print(latest)
    
    finally:
        vision.cleanup()