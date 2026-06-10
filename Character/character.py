from characterDefinitions import *
from faceDefinitions import *
if HAS_FACE:
    print('Importing Face module')
    from face import Face
if HAS_SPEECH:
    print('Importing Speech module')
    from speech import Speech
if HAS_HEARING:
    print('Importing Hearing module')
    from hearing import Hearing
    # from hearing import Hearing
if HAS_VISEME:
    print('Importing Viseme module')
    from viseme import Viseme
if HAS_VISION:
    print('Importing Vision module')
    from vision import Vision
    # from newvision import Vision
if HAS_MOVEMENT:
    print('Importing Movement module')
    from movement import Movement
if HAS_CONVERSATION:
    print('Importing Conversation module')
    from conversation import Conversation
import threading
import numpy as np
from scipy.interpolate import Rbf
from os.path import exists
import json
import time
import random

class VoiceEncoderRKNN:
    """
    RKNN implementation of Resemblyzer VoiceEncoder for the Orange Pi 5 Pro NPU.
    Loads a compiled 'voice-encoder.rknn' model and runs NPU inference.
    """
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = CHARACTER_FOLDER + "../Resources/voice-encoder.rknn"
        
        from rknnlite.api import RKNNLite
        self.rknn = RKNNLite()
        print(f"[Speaker Recognition] Loading VoiceEncoder RKNN model from {model_path}...")
        ret = self.rknn.load_rknn(model_path)
        if ret != 0:
            raise RuntimeError(f"Failed to load VoiceEncoder RKNN model (code {ret})")
        ret = self.rknn.init_runtime()
        if ret != 0:
            raise RuntimeError(f"Failed to init RKNN runtime (code {ret})")
        print("[Speaker Recognition] VoiceEncoder RKNN loaded successfully.")

    def embed_utterance(self, wav: np.ndarray) -> np.ndarray:
        """Extract speaker embedding from processed wav using RKNN NPU."""
        try:
            # Feature extraction on CPU: Wav to Mel Spectrogram using Resemblyzer if installed
            from resemblyzer.audio import wav_to_mel_spectrogram
            mel = wav_to_mel_spectrogram(wav)  # Shape (frames, 40)
            
            # Most RKNN models require float32 and batch dimension
            feats = mel[np.newaxis, :, :].astype(np.float32)  # Shape: (1, T, 40)
            
            outputs = self.rknn.inference(inputs=[feats])
            if outputs is None or len(outputs) == 0:
                return np.zeros(256, dtype=np.float32)
                
            embedding = outputs[0].flatten().copy()
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            print(f"[Speaker Recognition] NPU inference error: {e}")
            return np.zeros(256, dtype=np.float32)

    def release(self):
        if hasattr(self, 'rknn'):
            self.rknn.release()


class Character():
    def __init__(self, character_name="fuzzy", child=False, gender='female',
                 full_screen=True, wakeup=False, activity=None, languages=['en']):
        print("Initializing character ...")
        if HAS_FACE:
            self.face = Face(character=character_name, full_screen=IS_ROBOT and full_screen)
            if wakeup:
                self.face.generate_face(parts_selected=basic_sequences["idle"])
        else:
            self.face = None
        if HAS_SPEECH:
            self.speech = Speech(child=child, gender=gender, languages=languages)
        else:
            self.speech = None
        if HAS_VISEME:
            self.viseme = Viseme(face=self.face, speech=self.speech)
            self.viseme.character = self
        else:
            self.viseme = None
        
        if HAS_HEARING:
            self.hearing = Hearing()
        else:
            self.hearing = None
        if HAS_VISION:
            self.vision = Vision()
        else:
            self.vision = None

        if HAS_MOVEMENT:
            try:
                self.movement = Movement()
                if wakeup:
                    self.movement.home_position()
            except Exception as e:
                import traceback
                print(f"[Movement init failed]: {e}")
                traceback.print_exc()
                self.movement = None
        else:
            self.movement = None

        if HAS_CONVERSATION:
            self.conversation = Conversation()
            self.conversation.character = self
            self.conv = self.conversation
        else:
            self.conversation = None
            self.conv = None

        self.current_speaker = None
        self.activity_log = []

        self.lookat_calibration = None
        if self.face and self.movement and self.vision:
            if exists(CHARACTER_FOLDER + "lookat_calibrated.json"):
                self.lookat_calibration = json.load(open(CHARACTER_FOLDER + "lookat_calibrated.json"))
                # keys = head position (-1.0, 1.0)
                # values = detected face offset (-1.0, 1.0)
        
        self.set_activity(activity_name=activity)
        
        self.egocentric_db = {}
        if exists(CHARACTER_FOLDER + "egocentric_locations.json"):
            try:
                with open(CHARACTER_FOLDER + "egocentric_locations.json", "r") as f:
                    self.egocentric_db = json.load(f)
                print(f"Loaded {len(self.egocentric_db)} egocentric location entries.")
            except Exception as e:
                print(f"Error loading egocentric locations: {e}")

        # Speaker recognition database and encoder lazy load
        self.speaker_gaze_target = None
        self.voice_encoder = None
        self.speaker_db = None
        
        # Load NPU execution flags from characterDefinitions
        from characterDefinitions import USE_NPU_SPEAKER
        self.use_npu_speaker = USE_NPU_SPEAKER
        
        try:
            from make_friends import SpeakerDatabase
            db_path = CHARACTER_FOLDER + "../Resources/speaker_db.pkl"
            self.speaker_db = SpeakerDatabase(db_path=db_path)
            
            if self.use_npu_speaker:
                try:
                    self.voice_encoder = VoiceEncoderRKNN()
                    print("[OK] NPU-accelerated Speaker Recognition VoiceEncoder initialized.")
                except Exception as npu_err:
                    print(f"Warning: Failed to load NPU speaker encoder ({npu_err}). Falling back to CPU.")
                    self.use_npu_speaker = False
            
            if not self.use_npu_speaker:
                from resemblyzer import VoiceEncoder
                print("Loading CPU speaker recognition model in Character...")
                self.voice_encoder = VoiceEncoder()
                print("[OK] CPU Speaker recognition components initialized.")
                
        except Exception as e:
            print(f"Warning: Could not load speaker recognition: {e}")

        time.sleep(1)       # wait for all the initializations to complete
        print("Done initializing character!")

    def set_activity(self, activity_name=None):
        if activity_name:
            self.activity_name = activity_name.replace(" ", "_").replace("-", "_")
        else:
            self.activity_name = None
        print("DEBUG: ", self.activity_name)
        if self.face:
            self.face.set_activity(activity_name=self.activity_name)
        if self.speech:
            self.speech.set_activity(activity_name=self.activity_name)

    def run_character(self, face_data=None, audio_data=None, 
                      viseme_data=None, movement_data=None, 
                      caption_data=None,
                      image_data=None, video_data=None):
        # Check if the robot talks to a specific person in egocentric DB
        text_to_check = None
        if viseme_data and viseme_data.get('text'):
            text_to_check = viseme_data['text']
        elif audio_data and audio_data.get('text'):
            text_to_check = audio_data['text']
            
        if text_to_check:
            if not hasattr(self, 'activity_log'):
                self.activity_log = []
            if not self.activity_log or self.activity_log[-1].get('text') != text_to_check:
                self.activity_log.append({
                    "speaker": "Gigi",
                    "text": text_to_check,
                    "timestamp": time.time()
                })
            
            import re
            matched_name = None
            for name in self.egocentric_db.keys():
                if re.search(r'\b' + re.escape(name) + r'\b', text_to_check, re.IGNORECASE):
                    matched_name = name
                    break
            if matched_name:
                print(f"[Gaze Redirection] Matched '{matched_name}' in spoken text: '{text_to_check}'. Redirecting gaze.")
                self.lookat_person(matched_name)

        speech_thread = None
        movement_thread = None
        viseme_sequence = None

        # Kick off image preload in background during TTS generation (free parallelism)
        preload_thread = None
        if self.face and image_data:
            preload_thread = threading.Thread(
                target=self.face.preload_image,
                args=(image_data['filename'],),
                daemon=True
            )
            preload_thread.start()

        # Pre-generate audio synchronously, then use play_audio_thread so the
        # speech thread skips all TTS/loading work and goes straight to playback.
        if viseme_data and self.speech and self.viseme:
            audio_file = self.speech.update_audio_objects(file=viseme_data['file'], text=viseme_data['text'])
            viseme_sequence = self.viseme.generate_viseme_sequence(file=viseme_data['file'], text=viseme_data['text'])
            speech_thread = self.speech.play_audio_thread(file=audio_file)
        elif viseme_data and self.speech:
            speech_thread = self.speech.audio_thread(file=viseme_data['file'], text=viseme_data['text'])
        elif audio_data and self.speech:
            speech_thread = self.speech.audio_thread(file=audio_data['file'], text=audio_data['text'])

        if movement_data and self.movement:
            movement_thread = self.movement.movement_thread(motor_data=movement_data)
            movement_thread.start()

        # Wait for preload to finish, then display image from main thread (cv2 requirement)
        if preload_thread:
            preload_thread.join()
        if self.face and video_data:
            self.face.display_video_file(filename=video_data['filename'])
        elif self.face and image_data and self.face.preloaded_image is not None:
            self.face.show_face = False
            self.face.display_face(self.face.preloaded_image)
            self._cv_wait(image_data.get('duration', 1.5))

        # Viseme animation (or plain face) with speech
        if self.face:
            self.face.display_image_file(filename=None)  # restore character face
            face_parts = []
            if face_data:
                if 'parts' in face_data:
                    face_parts.append([0.5, face_data['parts']])
                elif 'sequence' in face_data:
                    face_parts.append([0.5, basic_sequences[face_data['sequence']]])
                self.face.guidance = face_data.get('guidance', None)
            else:
                self.face.guidance = None
            if viseme_sequence is not None:
                face_parts.append([self.speech.sample_rate, viseme_sequence])
            if len(face_parts) > 0:
                face_sequence, min_delay = self.face.combine_seuqences(sequences=face_parts)
                if speech_thread:
                    speech_thread.start()
                self.face.generate_face(parts_selected=face_sequence, stop_condition="face", delay=min_delay)
            elif speech_thread:
                speech_thread.start()
        elif speech_thread:
            speech_thread.start()

        if speech_thread:
            self._join_with_cv_loop(speech_thread)
        if movement_thread:
            movement_thread.join()

    def _cv_wait(self, seconds):
        """Sleep while keeping the OpenCV event loop alive."""
        if self.face and self.face.IMAGE_OPTION == "cv":
            import cv2
            end = time.time() + seconds
            while time.time() < end:
                cv2.waitKey(30)
        else:
            time.sleep(seconds)

    def _join_with_cv_loop(self, thread):
        """Join a thread while keeping the OpenCV event loop alive (required on Linux/OrangePi)."""
        if self.face and self.face.IMAGE_OPTION == "cv":
            import cv2
            while thread.is_alive():
                cv2.waitKey(30)
        thread.join()

    def stop_character(self):
        if self.vision:
            if self.vision.stop_event:
                self.vision.stop_vision()
        if self.face:
            self.face.stop_face()

    def lookat_coordinate(self, offset=0.0, verbose=True):
        # Because the camera is mounted on the torso, any face offset detected in the image
        # represents a relative angle with respect to the torso.
        T_c = self.movement.calc_normalized_angle(motor="torso") if self.movement else 0.0
        
        if verbose:
            print(f"\n[LookAt Path] Input Face Offset (centered x-coord): {offset:.4f}")
            print(f"[LookAt Path] Current Torso Angle: {T_c:.4f}")
        
        if self.lookat_calibration:
            # calibration keys are neck positions, which (at torso=0.0) correspond to absolute face angle
            # calibration values are list offsets [offset_x, offset_y]
            vision_coor = np.array([float(i[0]) for i in list(self.lookat_calibration.values())])
            motor_coor = np.array([float(i) for i in list(self.lookat_calibration.keys())])            
            
            # Map face offset to relative angle (neck coordinate space)
            rbf_interpolator = Rbf(vision_coor, motor_coor, smooth=0.05)
            relative_angle = float(rbf_interpolator(offset))
            if verbose:
                print(f"[LookAt Path] Calibrated relative angle (mapped): {relative_angle:.4f}")
            
            # Target room-relative coordinate is current torso position + relative offset angle
            target_gaze_angle = T_c + relative_angle
        else:
            # Fallback if not calibrated: assume offset is in [-0.5, 0.5] range, map to approx [-1.0, 1.0] motor space
            relative_angle = offset * 2.0
            if verbose:
                print(f"[LookAt Path] Uncalibrated relative angle (fallback): {relative_angle:.4f}")
            target_gaze_angle = T_c + relative_angle
            
        target_gaze_angle = np.clip(target_gaze_angle, -0.9, 0.9)
        if verbose:
            print(f"[LookAt Path] Target Torso Angle: {target_gaze_angle:.4f}")
        return target_gaze_angle

    def listen_backchannel(self, timeout=15):
        if self.hearing and self.face:
            self.speaker_gaze_target = None
            self.current_speaker = None
            self.hearing.clear_audio_buffer()
            stop_event = threading.Event()
            
            recognition_stop = threading.Event()
            rec_thread = threading.Thread(target=self._speaker_recognition_worker, args=(recognition_stop,), daemon=True)
            rec_thread.start()
            
            threading.Timer(timeout, stop_event.set).start()
            hearing_thread = self.hearing.hearing_thread(stop_event=stop_event)
            hearing_thread.start()
            try:
                while not stop_event.is_set():
                    if self.speaker_gaze_target is not None:
                        target_name = self.speaker_gaze_target
                        self.speaker_gaze_target = None
                        self.lookat_person(target_name)
                    self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
            finally:
                recognition_stop.set()
                rec_thread.join(timeout=1.0)
                hearing_thread.join()
                
                # Record transcription under the recognized speaker
                if self.current_speaker and self.hearing.texts:
                    final_text = self.hearing.texts[-1]
                    if self.speaker_db:
                        self.speaker_db.add_transcription_record(self.current_speaker, final_text)
                
                # Log transcription in activity log
                if self.hearing.texts:
                    final_text = self.hearing.texts[-1]
                    if not hasattr(self, 'activity_log'):
                        self.activity_log = []
                    self.activity_log.append({
                        "speaker": self.current_speaker or "Unknown",
                        "text": final_text,
                        "timestamp": time.time()
                    })

    def listen_fluid(self, timeout=30, n_transcripts=2, check_callback=None):
        if self.hearing and self.face:
            self.speaker_gaze_target = None
            self.current_speaker = None
            self.hearing.clear_audio_buffer()
            stop_event = threading.Event()
            
            recognition_stop = threading.Event()
            rec_thread = threading.Thread(target=self._speaker_recognition_worker, args=(recognition_stop,), daemon=True)
            rec_thread.start()
            
            # Timeout handler
            threading.Timer(timeout, stop_event.set).start()
            
            cb = check_callback
            if cb is None:
                if self.conversation:
                    def default_check_callback(text):
                        return self.conversation.check_fluid_done(text)
                    cb = default_check_callback
                else:
                    def dummy_callback(text):
                        return False
                    cb = dummy_callback
            
            # Use the new hearing_fluid_thread
            hearing_thread = self.hearing.hearing_fluid_thread(
                stop_event=stop_event, 
                check_callback=cb, 
                n_transcripts=n_transcripts
            )
            hearing_thread.start()
            
            try:
                while not stop_event.is_set():
                    if self.speaker_gaze_target is not None:
                        target_name = self.speaker_gaze_target
                        self.speaker_gaze_target = None
                        self.lookat_person(target_name)
                    self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
            finally:
                recognition_stop.set()
                rec_thread.join(timeout=1.0)
                hearing_thread.join()
                
                # Record transcription under the recognized speaker
                if self.current_speaker and self.hearing.texts:
                    final_text = self.hearing.texts[-1]
                    if self.speaker_db:
                        self.speaker_db.add_transcription_record(self.current_speaker, final_text)
                
                # Log transcription in activity log
                if self.hearing.texts:
                    final_text = self.hearing.texts[-1]
                    if not hasattr(self, 'activity_log'):
                        self.activity_log = []
                    self.activity_log.append({
                        "speaker": self.current_speaker or "Unknown",
                        "text": final_text,
                        "timestamp": time.time()
                    })

    def _speaker_recognition_worker(self, stop_event):
        """
        Background worker that periodically runs speaker recognition on the accumulated
        audio in the hearing buffer, matching against the speaker database.
        """
        if not self.voice_encoder or not self.speaker_db:
            return

        import numpy as np
        from resemblyzer import preprocess_wav
        
        print("[Speaker Recognition] Thread started.")
        last_recognized_name = None
        last_processed_len = 0
        
        while not stop_event.is_set():
            # Check every 1.0 second
            time.sleep(1.0)
            
            if stop_event.is_set() or not self.hearing:
                break
                
            raw_audio = self.hearing.get_full_audio()
            if raw_audio is None or len(raw_audio) < 16000:
                continue
                
            # Only process if new audio has been accumulated
            if len(raw_audio) == last_processed_len:
                continue
            last_processed_len = len(raw_audio)
            
            try:
                # Limit to the last 3.0 seconds (48,000 samples at 16kHz)
                # to keep embedding extraction real-time and constant-time (O(1)).
                raw_audio_slice = raw_audio[-48000:] if len(raw_audio) > 48000 else raw_audio
                
                # Preprocess and get embedding
                wav = preprocess_wav(raw_audio_slice)
                embedding = self.voice_encoder.embed_utterance(wav)
                
                # Identify speaker
                name, similarity = self.speaker_db.identify_speaker(embedding, threshold=0.75)
                if name:
                    self.current_speaker = name
                    if name != last_recognized_name:
                        print(f"[Speaker Recognition] Identified '{name}' (similarity: {similarity:.3f})")
                        last_recognized_name = name
                        self.speaker_gaze_target = name
            except Exception as e:
                print(f"[Speaker Recognition] Error: {e}")
        print("[Speaker Recognition] Thread stopped.")

    def idle(self, duration=-1.0):
        if self.face:
            stop_event = threading.Event()
            end_time = time.time() + duration if duration > 0 else float('inf')
            if duration > 0:
                threading.Timer(duration, stop_event.set).start()
            while not stop_event.is_set() and time.time() < end_time:
                self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)

    # def lookfor_backchannel(self, what=None):
    #     if self.vision and self.face:
    #         stop_event = threading.Event()
    #         vision_thread = self.vision.vision_thread(stop_event=stop_event, what=what)
    #         vision_thread.start()
    #         while not stop_event.is_set():
    #             self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
    #         vision_thread.join()

    def lookat_behavior(self, target_coor=0.0):
        """
        Coordinated Eye-Head-Torso gaze redirection based on physiological models.
        Citations:
        - Guitton, D. (1992). Control of eye-head coordination during orienting gaze shifts.
        - Land, M. F. (2004). The coordination of eye, head, and body movements in systematic tasks.
        - Flash, T., & Hogan, N. (1985). The coordination of arm movements: an experimentally confirmed mathematical model.
        """
        if not self.face or not self.movement:
            return

        # Current positions of torso and neck
        T_c = self.movement.calc_normalized_angle(motor="torso")
        N_c = self.movement.calc_normalized_angle(motor="neck")
        H_c = T_c + N_c
        
        # Target coordinate (total gaze angle)
        theta_target = target_coor
        
        # To put the face in the center of the camera image by moving the torso correctly,
        # the torso (which carries the camera) must align directly with the target coordinate.
        # This completely centers the face in the camera frame.
        T_final = np.clip(theta_target, -0.9, 0.9)
        N_final = 0.0
            
        H_target = T_final + N_final

        print(f"\n[LookAt Behavior] Start Motion Trajectory:")
        print(f"  Target coordinate: {theta_target:.4f}")
        print(f"  Current -> Torso: {T_c:.4f}, Neck: {N_c:.4f}, Head: {H_c:.4f}")
        print(f"  Target  -> Torso: {T_final:.4f}, Neck: {N_final:.4f}, Head: {H_target:.4f}")

        # Profile parameters (30Hz trajectory)
        fps = 30
        duration = 1.2
        num_steps = int(duration * fps)
        dt = 1.0 / fps
        
        # Eye direction threshold (VOR activation)
        eye_threshold = 0.12
        
        # Trajectory execution loop
        for i in range(num_steps):
            u = i / (num_steps - 1)
            
            # Minimum-jerk profile: S(u) = 10u^3 - 15u^4 + 6u^5
            S_u = 10 * (u**3) - 15 * (u**4) + 6 * (u**5)
            
            # Head orientation moves faster (simulating lower neck inertia and saccadic leading)
            u_head = min(1.0, u * 1.5)
            S_head = 10 * (u_head**3) - 15 * (u_head**4) + 6 * (u_head**5)
            
            # Compute current angles along the trajectory
            T_t = T_c + (T_final - T_c) * S_u
            H_t = H_c + (H_target - H_c) * S_head
            N_t = H_t - T_t
            
            if i % 10 == 0 or i == num_steps - 1:
                print(f"  Step {i:02d}/{num_steps}: Torso={T_t:.4f}, Neck={N_t:.4f}, Head={H_t:.4f}")

            # Send movement commands to motors (non-blocking)
            self.movement.move_motors({"torso": T_t, "neck": N_t})
            
            # VOR Eye control:
            # Check the error between head orientation and target
            gaze_error = H_target - H_t
            
            if gaze_error > eye_threshold:
                eye_seq = basic_sequences.get("look_left", basic_sequences["idle"])
            elif gaze_error < -eye_threshold:
                eye_seq = basic_sequences.get("look_right", basic_sequences["idle"])
            else:
                eye_seq = basic_sequences["idle"]
                
            # Render and display face frame in real-time
            face_state = {}
            for part in global_parts:
                if part in eye_seq:
                    part_data = eye_seq[part]
                    face_state[part] = (part_data[0], part_data[1][0])
                else:
                    face_state[part] = ("idle", "1")
            
            face_image = self.face.set_face(face_state)
            if self.vision:
                cam_frame = self.vision.get_latest_frame()
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
            
            time.sleep(dt)
            
        # Final safety check: set exact target positions
        self.movement.move_motors({"torso": T_final, "neck": N_final})
        # Set face back to idle
        self.face.run_sequence(face_sequence_name="idle")
        print(f"[LookAt Behavior] Motion finished. final Torso={T_final:.4f}, Neck={N_final:.4f}\n")

    def lookat_something(self, what="face", timeout=-1):
        # timeout - how long (seconds) to look for a face if one is not found
        start_time = time.time()
        if self.vision:            
            if self.lookat_calibration:     # if calibrated, look at something
                self.vision.look_and_stop(what=what, timeout=1)
                print("DEBUG: ", what, self.vision.found)                
                if len(self.vision.found[what]) > 0:
                    self.update_egocentric_locations()
                    self.vision.stop_vision()
                    offset_data = next(iter(self.vision.found[what].values()))["offset"]
                    offset_x, offset_y = offset_data[0], offset_data[1]
                    print(f"\n[LookAt Something] Detected target '{what}':")
                    print(f"  Raw screen offset: X={offset_x:.4f}, Y={offset_y:.4f} (centered coords)")
                    head_coor = self.lookat_coordinate(offset=offset_x)
                    self.lookat_behavior(target_coor=head_coor)
                    print("Found something!")
                    return True
                else:   # did not see a face
                    if timeout < 0:
                        print("Timed out")
                        return False
                    else:       # select a random side a look for that
                        head_coor = random.choice([1, 0, -1]) * FOLLOW_TORSO_OFFSET * 1.01
                        print(f"[LookAt Something] Target '{what}' not seen. Scanning at: {head_coor:.4f}")
                        self.lookat_behavior(target_coor=head_coor)
                        duration = time.time() - start_time
                        remaining_timeout = timeout - duration
                        print("Looking again ...")
                        return self.lookat_something(what=what, timeout=remaining_timeout)
            else:                           # if not calibrated, just report if found something
                self.vision.look_and_stop(what=what, timeout=timeout)
                return len(self.vision.found[what]) > 0
        return False

    def follow_face(self, timeout=-1, stop_event=None):
        """
        Face-tracking loop that minimizes servomotor noise.
        - Silent gaze (screen eyes) reacts immediately (30Hz) to track small face movements.
        - Neck moves only when face eccentricity relative to the head exceeds a deadband (0.12).
        - Torso moves only when face eccentricity relative to the camera exceeds a large deadband (0.25).
        - Both neck and torso movements are throttled by cooldowns and damping factors to minimize noise.
        """
        if not self.vision:
            print("Vision not enabled, cannot follow face.")
            return

        print("Starting noise-minimizing face tracking...")
        was_running = self.vision.running
        if not was_running:
            self.vision.run_vision()

        # Control timing and state variables
        dt = 0.05  # 20 Hz tracking rate
        last_torso_move_time = 0.0
        last_neck_move_time = 0.0
        torso_cooldown = 2.5
        neck_cooldown = 1.0
        
        lost_face_start = None
        home_returned = False
        search_dir = 1.0
        start_time = time.time()
        frame_count = 0

        try:
            while True:
                # Check cancellation signals
                if stop_event and stop_event.is_set():
                    print("Face tracking stopped via stop event.")
                    break
                if timeout > 0 and (time.time() - start_time) > timeout:
                    print("Face tracking timed out.")
                    break

                last_data = self.vision.get_last_data()
                if len(last_data) > 0:
                    self.update_egocentric_locations()
                    # Reset face lost tracking
                    lost_face_start = None
                    home_returned = False
                    frame_count += 1

                    # Prioritize recognized faces over Unknown/Recognizing ones to avoid background distraction
                    face_info = None
                    for f_info in last_data.values():
                        if f_info.get('name', 'Unknown') not in ['Unknown', 'Recognizing...']:
                            face_info = f_info
                            break
                    if face_info is None:
                        face_info = next(iter(last_data.values()))

                    offset_x = face_info.get('offset', [0.0, 0.0])[0]
                    offset_y = face_info.get('offset', [0.0, 0.0])[1]

                    # Read current motor angles
                    T_c = self.movement.calc_normalized_angle(motor="torso") if self.movement else 0.0
                    N_c = self.movement.calc_normalized_angle(motor="neck") if self.movement else 0.0

                    # Calculate target coordinate using calibration (or fallback)
                    # This maps offset_x to relative_angle in motor space with the correct sign
                    T_target = self.lookat_coordinate(offset=offset_x, verbose=False)
                    relative_angle = T_target - T_c

                    # Print variables during face tracking
                    if frame_count % 10 == 0:
                        print(f"[Follow Face Log] Screen Offset: X={offset_x:+.4f}, Y={offset_y:+.4f} | Calibrated Relative Angle: {relative_angle:+.4f}")
                        print(f"                  Current Angles: Torso={T_c:.4f}, Neck={N_c:.4f}")

                    # Calculate target coordinates and errors for VOR
                    error_head = relative_angle - N_c

                    # 1. Silent Eye Gaze Update (render immediately, 0 motor noise)
                    if self.face:
                        if error_head > 0.12:
                            eye_seq = basic_sequences.get("look_left", basic_sequences["idle"])
                        elif error_head < -0.12:
                            eye_seq = basic_sequences.get("look_right", basic_sequences["idle"])
                        else:
                            eye_seq = basic_sequences["idle"]

                        face_state = {}
                        for part in global_parts:
                            if part in eye_seq:
                                part_data = eye_seq[part]
                                face_state[part] = (part_data[0], part_data[1][0])
                            else:
                                face_state[part] = ("idle", "1")
                        
                        face_image = self.face.set_face(face_state)
                        if self.vision:
                            cam_frame = self.vision.get_latest_frame()
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

                    # 2. Torso Movement Decision (reduce deadband to 0.05, increase factor to 0.95 for centering)
                    T_new = T_c
                    if abs(relative_angle) > 0.05:
                        if time.time() - last_torso_move_time > torso_cooldown:
                            delta_T = relative_angle * 0.95
                            T_new = np.clip(T_c + delta_T, -0.9, 0.9)
                            last_torso_move_time = time.time()
                            print(f"[Follow Face Log] Torso move triggered: {T_c:.4f} -> {T_new:.4f} (delta={delta_T:+.4f})")

                    # 3. Neck Movement Decision (medium deadband, medium cooldown)
                    # Neck aligns head orientation relative to the torso
                    N_target = relative_angle - (T_new - T_c)
                    N_new = N_c
                    if abs(N_target - N_c) > 0.12:
                        if time.time() - last_neck_move_time > neck_cooldown:
                            N_new = np.clip(N_c + (N_target - N_c) * 0.5, -0.9, 0.9)
                            last_neck_move_time = time.time()
                            print(f"[Follow Face Log] Neck move triggered: {N_c:.4f} -> {N_new:.4f}")

                    # Commit movements if updated
                    if (T_new != T_c or N_new != N_c) and self.movement:
                        self.movement.move_motors({"torso": T_new, "neck": N_new})

                else:
                    # No face detected
                    if self.face:
                        self.face.run_sequence(face_sequence_name="idle")

                    if lost_face_start is None:
                        lost_face_start = time.time()
                    elif time.time() - lost_face_start > 5.0:
                        if self.movement:
                            T_c = self.movement.calc_normalized_angle(motor="torso")
                            # Slowly sweep torso between -0.9 and 0.9 to search for a face
                            search_speed = 0.1  # units per second
                            T_new = T_c + search_dir * search_speed * dt
                            if T_new >= 0.9:
                                T_new = 0.9
                                search_dir = -1.0
                            elif T_new <= -0.9:
                                T_new = -0.9
                                search_dir = 1.0
                            
                            # Keep neck centered during search so camera aligns with torso direction
                            self.movement.move_motors({"torso": T_new, "neck": 0.0})
                            if frame_count % 10 == 0:
                                print(f"[Follow Face Log] Searching for face... Torso={T_new:.4f}, dir={search_dir}")

                # OpenCV wait to keep GUI responsive, otherwise standard sleep
                if self.face and self.face.IMAGE_OPTION == "cv":
                    import cv2
                    cv2.waitKey(int(dt * 1000))
                else:
                    time.sleep(dt)

        finally:
            if not was_running:
                self.vision.stop_vision()
            if self.face:
                self.face.run_sequence(face_sequence_name="idle")

    def update_egocentric_locations(self):
        """
        Scans current face tracking data, and if any recognized face is present,
        updates the persistent egocentric location database with their room angle.
        """
        if not self.vision:
            return
        last_data = self.vision.get_last_data()
        updated = False
        for face_id, face_info in last_data.items():
            name = face_info.get('name', 'Unknown')
            if name not in ['Unknown', 'Recognizing...']:
                offset = face_info.get('offset', [0.0, 0.0])
                offset_x = offset[0]
                # Calculate absolute egocentric angle (combining current torso angle and calibrated face offset)
                target_gaze_angle = self.lookat_coordinate(offset=offset_x, verbose=False)
                if target_gaze_angle is not None:
                    self.egocentric_db[name] = {
                        "angle": float(target_gaze_angle),
                        "timestamp": time.time()
                    }
                    updated = True
        if updated:
            try:
                with open(CHARACTER_FOLDER + "egocentric_locations.json", "w") as f:
                    json.dump(self.egocentric_db, f, indent=4)
            except Exception as e:
                print(f"Error saving egocentric locations: {e}")

    def lookat_person(self, name):
        """
        Looks up a person by name in the egocentric database, and moves the robot's
        gaze (neck and torso) to look at their last known physical location.
        """
        if name in self.egocentric_db:
            target_angle = self.egocentric_db[name]["angle"]
            print(f"Looking at '{name}' at last known egocentric location: {target_angle:.3f}")
            self.lookat_behavior(target_coor=target_angle)
            return True
        else:
            print(f"Person '{name}' not found in egocentric database.")
            return False

    def conversational_turn(self, file):
        if self.viseme:
            self.viseme.run_viseme(file=file)
            self.listen_backchannel()

    def ask_for_something(self, what=None, file=None):
        if self.viseme:
            self.viseme.run_viseme(file=file)
            self.lookfor_backchannel(what=what)

    def full_conversation(self):
        if self.viseme and self.conversation:
            agent_text = "What do you want to talk about"
            system_prompt = "Your name is Gigi, a social robot teaching assistant. You are going to interact with children in a friendly and engaging manner. You are perky, curious and generally happy. Reply with ONE short conversational sentence. Do NOT use lists, bullet points, or numbers. Do NOT give multiple ideas or explanations. Speak naturally as if talking out loud. Stop immediately after the first sentence."
            for i in range(2):
                print("Agent: ", agent_text)
                self.viseme.run_viseme(text=agent_text)
                self.listen_backchannel()
                user_text = self.hearing.texts[-1]
                print("User: ", user_text)
                agent_text = self.conversation.get_response(system_prompt=system_prompt, user_prompt=user_text)
        


if __name__ == "__main__":
    fuzzy = Character()
    
    print("\n--- Testing Fluid Listening ---")
    test_question = "Can you tell me a little bit about your favorite animal and why you like it?"
    print(f"Robot: {test_question}")
    # Prime the conversation history so the LLM evaluator knows what it is evaluating against
    if fuzzy.conversation:
        fuzzy.conversation.conversation_history.append({"role": "assistant", "content": test_question})
    
    print("Start speaking! Keep talking until the AI decides you have answered the question.")
    fuzzy.listen_fluid(timeout=30, n_transcripts=2)
    
    if fuzzy.hearing and fuzzy.hearing.texts:
        print(f"\nFinal transcribed text: {fuzzy.hearing.texts[-1]}")
    print("--- End Fluid Listening Test ---\n")

    # fuzzy.conversational_turn(file="Assets/audio/demo_01_greetings.wav")
    # fuzzy.lookfor_backchannel()
    # fuzzy.full_conversation()
    # fuzzy.listen_backchannel()
    # fuzzy.movement.home_position()
    # fuzzy.lookat_something(timeout=10)
    # fuzzy.lookat_something(timeout=10)
    # fuzzy.lookat_something(timeout=10)

