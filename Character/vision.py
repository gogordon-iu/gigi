import cv2
import time
import threading
from queue import Queue, Empty
import vision_helper as vh

class Vision:
    def __init__(self, camera_source=None, auto_start=False):
        self.camera_source = camera_source
        self.cap = None
        self.is_robot = True

        self.face_db = vh.FaceDatabase()
        self.emotion_detector = vh.EmotionDetector()
        self.face_cache = vh.ImprovedFaceCache()

        self.timestamped_data = {}
        self.last_data = {}

        self.face_mesh = None
        self.hands = None

        self.face_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.emotion_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.gesture_queue = Queue(maxsize=vh.MAX_QUEUE_SIZE)
        self.result_queue = Queue()

        self.stop_event = threading.Event()
        self.capture_thread = None
        self.vision_thread = None
        self.running = False

        self.processing_flags = {'face_detection': 5, 'face_recognition': 5, 'emotion': 5, 'gesture': 5}
        self.gesture_names = {0: "Unknown", 1: "Thumbs Up", 2: "Thumbs Down"}
        self.hand_gesture = "Unknown"

        self.active_workers = {'face_recognition': False, 'emotion': False, 'gesture': False}
        self.last_process_time = {'face_detection': 0, 'face_recognition': 0, 'emotion': 0, 'gesture': 0}

        self.threads = []
        self.latest_frame = None
        self.raw_frame = None
        self.frame_lock = threading.Lock()

        if auto_start:
            self.run_vision()
    
    @property
    def found(self):
        class FoundDict(dict):
            def __missing__(self, key):
                return self['face']
        
        fd = FoundDict()
        fd['face'] = self.last_data
        return fd
    
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

    def _capture_loop(self):
        self.cap = self.open_camera(self.camera_source) # cv2.VideoCapture(0)
        try:
            while not self.stop_event.is_set():
                ret, frame = self.cap.read()
                if not ret:
                    break
                with self.frame_lock:
                    self.raw_frame = frame.copy()
                time.sleep(0.01)
        finally:
            if self.cap:
                self.cap.release()
    def _display_loop(self):
        """Internal display loop that runs in a thread"""
        print("Display loop started. Press 'q' to quit...")

        # Create the window first
        cv2.namedWindow('Camera Feed', cv2.WINDOW_NORMAL)
        # Set it to fullscreen
        cv2.setWindowProperty('Camera Feed', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        
        while not self.stop_event.is_set():
            frame = self.get_latest_frame()
            if frame is not None:
                cv2.imshow('Camera Feed', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_event.set()
                    break
            time.sleep(0.01)
        cv2.destroyAllWindows()

    def display_loop(self):
        """Public method to run display loop in main thread (for backwards compatibility)"""
        if self.is_robot:
            print("Display disabled (is_robot=True)")
            return
        self._display_loop()
    def _vision_loop(self):
        while not self.stop_event.is_set():
            with self.frame_lock:
                frame = self.raw_frame.copy() if self.raw_frame is not None else None
            
            if frame is not None:
                processed_frame, _ = self._process_frame(frame)
                with self.frame_lock:
                    self.latest_frame = processed_frame
            
            time.sleep(0.001)
                
    def run_vision(self, show_window=True):
        """
        Start the vision system.
        """
        if not self.running:
            self.stop_event.clear()
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
            self.capture_thread.start()
            self.vision_thread.start()
            self.running = True
    
            if not self.is_robot and show_window:
                time.sleep(0.5)  # Give camera time to initialize
                self._display_loop()
            else:
                print("Vision running in background (is_robot=True or show_window=False)")
    
    def stop_vision(self):
        if self.running:
            self.stop_event.set()
            if self.capture_thread:
                self.capture_thread.join(timeout=2.0)
            if self.vision_thread:
                self.vision_thread.join(timeout=2.0)
            self.running = False
    
    def set_processing_flags(self, flags):
        for key, value in flags.items():
            if key in self.processing_flags:
                self.processing_flags[key] = value
    
    def get_latest_frame(self):
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def get_last_data(self):
        return self.last_data.copy()
    
    def get_timestamped_data(self):
        return self.timestamped_data.copy()
    
    def look_and_stop(self, what, timeout=5.0, show_camera_feed=True):
        result = self.look_for(what, timeout, show_camera_feed)
        
        return result

    def look_for(self, what, timeout=5.0, show_camera_feed=True):
        result_container = {'found': False, 'data': None, 'done': False}
        stop_event = threading.Event()
        search_thread = threading.Thread(target=vh.VisionHelpers.look_for_worker,
                                         args=(what, timeout, result_container, stop_event, self.get_last_data),
                                         daemon=True)
        search_thread.start()
        
        # While searching, continuously overlay the camera feed on Gigi's face screen in real-time
        dt = 0.05
        from faceDefinitions import global_parts
        import numpy as np
        while not result_container['done']:
            if getattr(self, 'face', None):
                # Draw the default face frame (idle sequence)
                face_state = {part: ("idle", "1") for part in global_parts}
                face_image = self.face.set_face(face_state)
                
                # Fetch latest frame and overlay
                show_feed = show_camera_feed and getattr(getattr(self, 'gigi', None), 'show_camera_feed', True)
                if show_feed:
                    cam_frame = self.get_latest_frame()
                    if cam_frame is not None:
                        import cv2
                        if self.face.IMAGE_OPTION == "cv":
                            h, w = face_image.shape[:2]
                            cam_h, cam_w = cam_frame.shape[:2]
                            scale_w = int(w * 0.25)
                            scale_h = int(cam_h * scale_w / cam_w)
                            cam_resized = cv2.resize(cam_frame, (scale_w, scale_h))
                            face_image[h - scale_h:h, w - scale_w:w] = cam_resized
                        elif self.face.IMAGE_OPTION == "pygame":
                            import pygame
                            rgb_frame = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
                            cam_h, cam_w = rgb_frame.shape[:2]
                            scale_w = int(face_image.get_width() * 0.25)
                            scale_h = int(cam_h * scale_w / cam_w)
                            rgb_resized = cv2.resize(rgb_frame, (scale_w, scale_h))
                            pg_cam = pygame.image.fromstring(rgb_resized.tobytes(), (scale_w, scale_h), "RGB")
                            face_image.blit(pg_cam, (face_image.get_width() - scale_w, face_image.get_height() - scale_h))
                
                self.face.display_face(face_image)
            
            # Proportional non-blocking face tracking during look_for
            gigi = getattr(self, 'gigi', None)
            if gigi and self.running:
                last_data = self.get_last_data()
                if last_data:
                    face_info = next(iter(last_data.values()))
                    offset_x = face_info.get('offset', [0.0, 0.0])[0]
                    
                    T_c = gigi.movement.calc_normalized_angle(motor="torso") if gigi.movement else 0.0
                    N_c = gigi.movement.calc_normalized_angle(motor="neck") if gigi.movement else 0.0
                    
                    T_target = gigi.lookat_coordinate(offset=offset_x, verbose=False)
                    relative_angle = T_target - T_c
                    
                    delta_T = relative_angle * 0.15
                    T_next = np.clip(T_c + delta_T, -0.9, 0.9)
                    
                    N_target = relative_angle - (T_next - T_c)
                    delta_N = (N_target - N_c) * 0.35
                    N_next = np.clip(N_c + delta_N, -0.9, 0.9)
                    
                    if gigi.movement:
                        gigi.movement.move_motors({"torso": T_next, "neck": N_next})
            time.sleep(dt)
            
        return {'found': result_container['found'], 'data': result_container['data']}
    
    def should_process(self, feature, fps):
        if fps <= 0:
            return False
        current_time = time.time()
        time_per_frame = 1.0 / fps
        if current_time - self.last_process_time[feature] >= time_per_frame:
            self.last_process_time[feature] = current_time
            return True
        return False
    
    def start_worker_if_needed(self, worker_type):
        if self.active_workers[worker_type]:
            return
        
        if worker_type == 'face_recognition':
            t = threading.Thread(target=vh.face_recognition_worker, 
                               args=(self.face_queue, self.result_queue, self.stop_event, self.face_db), daemon=True)
        elif worker_type == 'emotion':
            t = threading.Thread(target=vh.emotion_detection_worker, 
                               args=(self.emotion_queue, self.result_queue, self.stop_event, self.emotion_detector), daemon=True)
        elif worker_type == 'gesture':
            t = threading.Thread(target=vh.gesture_recognition_worker,
                               args=(self.gesture_queue, self.result_queue, self.stop_event, self.gesture_names), daemon=True)
        else:
            return
        
        t.start()
        self.threads.append(t)
        self.active_workers[worker_type] = True
    
    def initialize_face_detection(self):
        if self.face_mesh is None:
            self.face_mesh = vh.MediaPipeInitializers.initialize_face_mesh()
    
    def initialize_gesture_detection(self):
        if self.hands is None:
            self.hands = vh.MediaPipeInitializers.initialize_hands()
    
    def process_results(self):
        while True:
            try:
                result = self.result_queue.get_nowait()
                if result[0] == 'recognition':
                    closest_name = "None"
                    closest_dist = 1.0
                    if len(result) == 8:
                        _, face_id, name, is_new, position_key, timestamp, closest_name, closest_dist = result
                    else:
                        _, face_id, name, is_new, position_key, timestamp = result
                    self.face_cache.update_face_name(face_id, name, position_key)
                    self.face_cache.update_face(face_id, 'closest_name', closest_name)
                    self.face_cache.update_face(face_id, 'closest_dist', closest_dist)
                elif result[0] == 'emotion':
                    _, face_id, emotion, timestamp = result
                    self.face_cache.update_face(face_id, 'emotion', emotion)
                elif result[0] == 'gesture':
                    _, hand_type, gesture_name, timestamp = result
                    self.hand_gesture = gesture_name
            except Empty:
                break
            except:
                break
    
    def _process_frame(self, frame):
        try:
            current_time = time.time()
            h, w = frame.shape[:2]
            
            face_detection = self.should_process('face_detection', self.processing_flags['face_detection'])
            emotion = self.should_process('emotion', self.processing_flags['emotion'])
            gesture = self.should_process('gesture', self.processing_flags['gesture'])
            face_recognition = self.should_process('face_recognition', self.processing_flags['face_recognition'])
            
            self.process_results()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            if face_detection:
                self.initialize_face_detection()
                
                # Start face recognition worker if needed
                if face_recognition:
                    self.start_worker_if_needed('face_recognition')
                
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
                                if face_recognition and self.face_cache.needs_recognition(face_id) and not self.face_queue.full():
                                    try:
                                        position_key = self.face_cache.get_position_key(x_center, y_center)
                                        self.face_queue.put_nowait((face_id, face_crop.copy(), position_key, current_time))
                                    except:
                                        pass
                                
                                if emotion:
                                    self.start_worker_if_needed('emotion')
                                    if current_time - face_data.get('last_emotion', 0) > 5.0 and not self.emotion_queue.full():
                                        try:
                                            self.emotion_queue.put_nowait((face_id, face_crop.copy(), current_time))
                                        except:
                                            pass
                            
                            face_data = self.face_cache.get_face_data(face_id)
                            vh.VisionHelpers.draw_face_info(frame, x_min, y_min, x_max, y_max, face_data)
                except:
                    pass
            
            if gesture:
                self.initialize_gesture_detection()
                self.start_worker_if_needed('gesture')
                
                try:
                    hand_results = self.hands.process(rgb)
                    if hand_results.multi_hand_landmarks and hand_results.multi_handedness:
                        for hand_landmarks, handedness in zip(hand_results.multi_hand_landmarks, hand_results.multi_handedness):
                            hand_type = handedness.classification[0].label
                            wrist = hand_landmarks.landmark[0]
                            hand_x = wrist.x
                            hand_y = wrist.y
                            
                            for idx in [4, 8, 12, 16, 20, 0]:
                                landmark = hand_landmarks.landmark[idx]
                                cx, cy = int(landmark.x * w), int(landmark.y * h)
                                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
                            
                            if not self.gesture_queue.full():
                                try:
                                    self.gesture_queue.put_nowait((hand_landmarks.landmark, hand_type, current_time))
                                except:
                                    pass
                            
                            all_faces = self.face_cache.get_all_faces()
                            closest_face_id = vh.VisionHelpers.associate_gesture_to_face(hand_x, hand_y, w, h, all_faces)
                            if closest_face_id is not None and self.hand_gesture != "Unknown":
                                self.face_cache.update_face(closest_face_id, 'gesture', self.hand_gesture)
                except:
                    pass
            
            if face_detection and current_time % 30 == 0:
                self.face_cache.cleanup_old_faces()
            
            vh.VisionHelpers.update_data_structure(self.face_cache, self.last_data, self.timestamped_data, w, h)
            
            gigi = getattr(self, 'gigi', None)
            if gigi and self.running:
                try:
                    gigi.update_egocentric_locations()
                except Exception as e:
                    print(f"Error in automatic egocentric location update: {e}")
                    
            return frame, self.get_last_data()
        except:
            return frame, self.get_last_data()
        
        
    
    def cleanup(self):
        self.stop_vision()
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

if __name__ == "__main__":
    # vision = Vision(camera_source=None)
    # vision.is_robot = False
    # vision.set_processing_flags({'face_detection': 8.0, 'face_recognition': 8.0, 'emotion': 8.0, 'gesture': 2.0})
    # vision.run_vision()
    # #found = vision.look_for(what={"name": "Stephanie"}, timeout=60)
    # #print(f'Found: {found}')

    # # try:
    # #     while not vision.stop_event.is_set():
    # #         # found = vision.look_for(what={"name": "Someone"}, timeout=10)
    # #         # print(f'Found: {found}')

    # #         time.sleep(0.1)
    # # finally:
    # #     vision.stop_vision()
    # #     vision.cleanup()
    
    vision = Vision(camera_source=None)
    vision.is_robot = False
    vision.set_processing_flags({
        'face_detection': 8.0, 
        'face_recognition': 8.0, 
        'emotion': 8.0, 
        'gesture': 2.0
    })
    vision.run_vision()
    
    try:
        vision.display_loop()  # This runs in main thread
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        vision.cleanup()