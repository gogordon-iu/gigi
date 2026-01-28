import time
import re
import threading
import numpy as np
import pickle
import os
from Character.vision import Vision
from speech import Speech
from Character.hearing import Hearing
from conversation import Conversation
from resemblyzer import VoiceEncoder, preprocess_wav
from scipy.spatial.distance import cosine

class SpeakerDatabase:
    """Simple database to store speaker embeddings alongside names."""
    def __init__(self, db_path="../Resources/speaker_db.pkl"):
        self.db_path = db_path
        self.speaker_data = {}  # {name: embedding}
        self.load_database()
    
    def load_database(self):
        """Load speaker database from disk."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    self.speaker_data = pickle.load(f)
                print(f"✓ Loaded {len(self.speaker_data)} speaker profiles from {self.db_path}")
            except Exception as e:
                print(f"⚠ Error loading speaker database: {e}")
                self.speaker_data = {}
        else:
            print(f"No existing speaker database found at {self.db_path}")
    
    def save_database(self):
        """Save speaker database to disk."""
        try:
            with open(self.db_path, 'wb') as f:
                pickle.dump(self.speaker_data, f)
            print(f"✓ Saved speaker database to {self.db_path}")
        except Exception as e:
            print(f"✗ Error saving speaker database: {e}")
    
    def add_speaker(self, name, embedding):
        """Add or update a speaker embedding."""
        self.speaker_data[name] = embedding
        self.save_database()
    
    def identify_speaker(self, embedding, threshold=0.75):
        """
        Identify speaker from embedding.
        
        Args:
            embedding: Speaker embedding to identify
            threshold: Similarity threshold (0-1, higher = stricter)
            
        Returns:
            (name, similarity) or (None, 0) if no match
        """
        if not self.speaker_data:
            return None, 0
        
        best_match = None
        best_similarity = 0
        
        for name, stored_embedding in self.speaker_data.items():
            similarity = 1 - cosine(embedding, stored_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name
        
        if best_similarity >= threshold:
            return best_match, best_similarity
        else:
            return None, best_similarity


class FaceRegistrationDemo:
    def __init__(self, pause_vision_during_stt=True):
        # Initialize components
        self.vision = Vision(None, auto_start=False)
        self.vision.is_robot = True  # Set to True to prevent blocking
        self.vision.set_processing_flags({
            'face_detection': 8.0,
            'face_recognition': 8.0,
            'emotion': 0,  # Don't need emotion for this demo
            'gesture': 8.0
        })
        
        self.speech = Speech(languages="en", child=False)
        self.speech.set_activity("face_registration")
        
        self.hearing = Hearing(verbose=True)
        
        # Initialize LLM conversation with custom system prompt for name extraction
        name_extraction_prompt = (
            "You are Gigi, a helpful assistant for face registration. "
            "When the user tells you their name, extract ONLY the person's name from their response. "
            "Return just the name, nothing else. "
            "For example, if they say 'My name is John Smith' or 'I'm John Smith' or 'John Smith', "
            "you should return only: John Smith"
        )
        self.llm = Conversation(system_prompt=name_extraction_prompt)
        
        # NEW: Initialize speaker recognition
        print("Loading speaker recognition model...")
        self.voice_encoder = VoiceEncoder()
        self.speaker_db = SpeakerDatabase()
        print("✓ Speaker recognition ready")
        
        # Demo parameters
        self.unknown_threshold = 5.0  # seconds to confirm it's a new face
        self.pause_vision_during_stt = pause_vision_during_stt  # Performance optimization
        
        # Store captured face data
        self.captured_face_crop = None
        self.captured_face_encoding = None
        self.registering_face_id = None
        
        # NEW: Store captured speaker data
        self.captured_speaker_embedding = None
        
        # Display control
        self.demo_running = True
    
    def extract_speaker_embedding(self, audio_array):
        """
        Extract speaker embedding from audio using resemblyzer.
        
        Args:
            audio_array: numpy array of float32 audio at 16kHz
            
        Returns:
            Speaker embedding (256-dimensional vector) or None
        """
        try:
            if audio_array is None or len(audio_array) < 16000:  # Need at least 1 second
                print("✗ Audio too short for speaker recognition (need 1+ seconds)")
                return None
            
            print(f"Extracting speaker embedding from {len(audio_array)/16000:.1f}s of audio...")
            
            # Preprocess audio for resemblyzer (handles normalization)
            wav = preprocess_wav(audio_array)
            
            # Extract embedding
            embedding = self.voice_encoder.embed_utterance(wav)
            
            print(f"✓ Speaker embedding extracted: {len(embedding)} dimensions")
            return embedding
            
        except Exception as e:
            print(f"✗ Error extracting speaker embedding: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_name_from_speech(self, text):
        """Extract name from speech text using LLM with fallback to pattern matching."""
        text = text.strip()
        
        if not text:
            return None
        
        try:
            # Try LLM first
            prompt = f"Extract only the person's name from this text: '{text}'"
            response = self.llm.get_response_with_tts_sync(prompt)
            
            # Clean up the response
            name = response.strip()
            
            # Basic validation - check if response looks like a name
            # (should not be too long or contain weird characters)
            if name and len(name) < 50 and not any(char in name for char in ['?', '!', '.']) and name != "Connection issue.":
                print(f"LLM extracted name: '{name}'")
                return name
            else:
                print(f"LLM response doesn't look like a name: '{name}'")
                print("Falling back to pattern matching...")
                return self._extract_name_fallback(text)
                
        except Exception as e:
            print(f"Error extracting name with LLM: {e}")
            print("Falling back to pattern matching...")
            return self._extract_name_fallback(text)
    
    def _extract_name_fallback(self, text):
        """Fallback method to extract name using simple pattern matching."""
        text = text.lower().strip()
        
        # Common patterns for name responses
        patterns = [
            r"(?:my name is|i'm|i am|this is|call me)\s+([a-z]+(?:\s+[a-z]+)*)",
            r"^([a-z]+(?:\s+[a-z]+)*)$",  # Just the name
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Capitalize each word
                name = ' '.join(word.capitalize() for word in name.split())
                
                # Filter out common non-name words
                non_names = ['the', 'a', 'an', 'hello', 'hi', 'yes', 'no']
                if name.lower() not in non_names and len(name) > 1:
                    print(f"Pattern matching extracted name: '{name}'")
                    return name
        
        print("Could not extract name from text")
        return None
    
    def pause_vision_processing(self):
        """Temporarily pause vision processing to free up resources."""
        print("⏸ Pausing vision processing...")
        if self.pause_vision_during_stt:
            # Completely disable all processing for maximum performance
            self.vision.set_processing_flags({
                'face_detection': 0,
                'face_recognition': 0,
                'emotion': 0,
                'gesture': 0
            })
            # Small delay to ensure processing stops
            time.sleep(0.2)
    
    def resume_vision_processing(self):
        """Resume vision processing after pause."""
        print("▶ Resuming vision processing...")
        if self.pause_vision_during_stt:
            self.vision.set_processing_flags({
                'face_detection': 0.0,
                'face_recognition': 0.0,
                'emotion': 0,
                'gesture': 15.0
            })
            # Small delay to let processing restart
            time.sleep(0.2)
    
    def capture_face_crop(self, face_id):
        """Capture face crop and encoding when unknown face is detected."""
        print(f"\n=== Capturing face crop for face ID {face_id} ===")
        
        import cv2
        import face_recognition
        
        try:
            # Get current frame with the face
            frame = self.vision.get_latest_frame()
            if frame is None:
                print("✗ No frame available")
                return None
            
            # Get face data from cache
            face_data = self.vision.face_cache.get_face_data(face_id)
            
            if not face_data or 'box' not in face_data:
                print(f"✗ Face data not found in cache for ID: {face_id}")
                return None
            
            # Extract face crop using the bounding box
            x_min, y_min, x_max, y_max = face_data['box']
            face_crop = frame[y_min:y_max, x_min:x_max]
            
            if face_crop.size == 0:
                print("✗ Invalid face crop")
                return None
            
            print(f"✓ Face crop captured: {face_crop.shape}")
            
            # Resize and convert for face_recognition
            small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
            face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
            
            # Extract face encoding
            print("Extracting face encoding...")
            face_encodings = face_recognition.face_encodings(face_crop_rgb)
            
            if not face_encodings:
                print("✗ Could not extract face encoding")
                return None
            
            print(f"✓ Face encoding extracted: {len(face_encodings[0])} dimensions")
            
            # Return both the crop and encoding
            return {
                'crop': face_crop,
                'encoding': face_encodings[0],
                'box': face_data['box']
            }
            
        except Exception as e:
            print(f"✗ Error capturing face crop: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def wait_for_unknown_face(self):
        """Wait until we detect an unknown face for X seconds and capture the face crop.
        
        Handles multiple unknown faces by tracking each separately and registering
        the first one that reaches the confirmation threshold.
        """
        print("\n=== Waiting for unknown face ===")
        print("Looking at camera to detect faces...")
        
        # Track multiple unknown faces separately
        unknown_faces_timers = {}  # {face_id: start_time}
        last_status = None
        
        while self.demo_running:
            # Get data directly from face cache for more accurate info
            all_faces = self.vision.face_cache.get_all_faces()
            data = self.vision.get_last_data()
            
            # Debug: Show what we're seeing
            current_status = f"Faces detected: {len(all_faces)}"
            if current_status != last_status:
                print(f"\n{current_status}")
                last_status = current_status
            
            # Get current unknown face IDs
            current_unknown_ids = set()
            
            if all_faces:
                for face_id, face_info in all_faces.items():
                    name = face_info.get('name', 'Unknown')
                    
                    # Check if face is Unknown OR matches face_xxxx pattern OR still being recognized
                    # A face is "unknown" if:
                    # 1. Name is explicitly "Unknown", OR
                    # 2. Name matches pattern "face_xxxx" (where xxxx is any 4-digit number), OR
                    # 3. Recognition was attempted and name is still "Recognizing..."
                    is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                    is_unknown = (name == 'Unknown' or 
                                 is_face_pattern or
                                 (name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
                    
                    if is_unknown:
                        current_unknown_ids.add(face_id)
                        
                        # Start timer for this face if not already tracking
                        if face_id not in unknown_faces_timers:
                            unknown_faces_timers[face_id] = time.time()
                            print(f"\n\nUnknown face detected (ID: {face_id}, name: '{name}'), starting timer...")
                        
                        # Check if this face has been confirmed long enough
                        elapsed = time.time() - unknown_faces_timers[face_id]
                        
                        # Show progress for all tracked faces
                        if len(unknown_faces_timers) > 1:
                            print(f"  Face {face_id}: {elapsed:.1f}s / {self.unknown_threshold}s", end='')
                            if face_id != list(all_faces.keys())[-1]:
                                print(" | ", end='')
                            else:
                                print("\r", end='')
                        else:
                            print(f"  Confirming unknown face {face_id}... {elapsed:.1f}s / {self.unknown_threshold}s", end='\r')
                        
                        # If this face reaches threshold, register it
                        if elapsed >= self.unknown_threshold:
                            print(f"\n✓ Confirmed unknown face {face_id} after {elapsed:.1f} seconds")
                            
                            if len(unknown_faces_timers) > 1:
                                print(f"  Note: {len(unknown_faces_timers)} unknown faces detected, registering face {face_id} first")
                            
                            # Set this as the face being registered (for green box)
                            self.registering_face_id = face_id
                            
                            # Capture face crop NOW while we have the detection
                            face_crop_data = self.capture_face_crop(face_id)
                            if face_crop_data:
                                # Store for later use
                                self.captured_face_crop = face_crop_data['crop']
                                self.captured_face_encoding = face_crop_data['encoding']
                                print("✓ Face crop and encoding stored for registration")
                                return face_id
                            else:
                                print("✗ Failed to capture face crop, restarting timer for this face...")
                                # Restart timer for this specific face
                                unknown_faces_timers[face_id] = time.time()
                                # Clear registering_face_id since capture failed
                                self.registering_face_id = None
                    else:
                        # Known face - if we were tracking it, remove it
                        if face_id in unknown_faces_timers:
                            print(f"\n\nFace {face_id} recognized as '{name}', removing from unknown list")
                            del unknown_faces_timers[face_id]
            
            # Clean up timers for faces that are no longer visible
            faces_to_remove = []
            for tracked_id in unknown_faces_timers.keys():
                if tracked_id not in current_unknown_ids:
                    faces_to_remove.append(tracked_id)
            
            for face_id in faces_to_remove:
                print(f"\n\nFace {face_id} no longer visible, removing from tracking")
                del unknown_faces_timers[face_id]
            
            time.sleep(0.2)
        
        return None
    
    def ask_for_name(self):
        """Ask for the person's name and get response with speaker embedding."""
        print("\n=== Asking for name ===")
        self.speech.run_speech(text="Hi! I'm Gigi. What's your name?")
        
        # Wait a moment for speech to complete
        time.sleep(2)
        
        # Pause vision processing to free up resources for speech-to-text
        self.pause_vision_processing()
        
        # Listen for response
        print("Listening for name...")
        self.hearing.texts = []  # Clear previous texts
        self.hearing.run_hearing()
         
        if len(self.hearing.texts) > 0:
            response = self.hearing.texts[-1]
            print(f"Heard: '{response}'")
            name = self.extract_name_from_speech(response)
            return name
        else:
            print("No response heard")
        
        return None
    
    def confirm_name(self, name):
        """Confirm the name using thumbs up/down gesture only."""
        print(f"\n=== Confirming name: {name} ===")
        
        # Clear all gesture data before starting
        print("Clearing old gesture data...")
        all_faces = self.vision.face_cache.get_all_faces()
        for face_id, face_info in all_faces.items():
            face_info['gesture'] = 'Unknown'
            face_info['gesture_timestamp'] = None
        
        self.speech.run_speech(text=f"Hi, {name}. Did I say it correctly? Give me a thumbs up or thumbs down.")
        
        # Wait a moment for speech to complete and user to prepare
        time.sleep(2)
        
        # Wait for NEW gesture
        print("Waiting for thumbs up or thumbs down gesture...")
        start_time = time.time()
        timeout = 15.0  # 15 seconds to respond
        gesture_seen = False
        
        while time.time() - start_time < timeout and self.demo_running:
            data = self.vision.get_last_data()
            all_faces = self.vision.face_cache.get_all_faces()
            
            # Check for gesture
            if all_faces:
                for face_id, face_info in all_faces.items():
                    gesture = face_info.get('gesture', 'Unknown')
                    
                    # Only accept gesture if it's NEW (appeared after we started waiting)
                    if gesture != 'Unknown' and not gesture_seen:
                        gesture_seen = True
                        print(f"\nDetected NEW gesture: {gesture}")
                        
                        if gesture == 'Thumbs Up':
                            print("✓ Got thumbs up!")
                            # Clear gesture before returning
                            face_info['gesture'] = 'Unknown'
                            return True
                        elif gesture == 'Thumbs Down':
                            print("✗ Got thumbs down!")
                            # Clear gesture before returning
                            face_info['gesture'] = 'Unknown'
                            return False
            
            # Show remaining time
            remaining = timeout - (time.time() - start_time)
            print(f"Waiting for gesture... {remaining:.1f}s remaining", end='\r')
            
            time.sleep(0.1)
        
        print("\nTimeout waiting for gesture")
        return None  # Return None for timeout to distinguish from False
    

    def capture_voice_enrollment(self, name):
        """Capture a voice sample for speaker recognition (records until silence)."""
        print(f"\n=== Capturing voice enrollment for {name} ===")
        
        script = "The quick brown fox jumps over the lazy dog"
        
        self.speech.run_speech(
            text=f"Great, {name}! Now, please repeat after me to register your voice: {script}"
        )
        
        # Wait for speech to complete
        time.sleep(3)
        
        # Pause vision processing to free up resources
        self.pause_vision_processing()
        
        # Listen for the repeated phrase (will record until silence detected)
        print(f"Listening for: '{script}'")
        print("(Recording will stop automatically after detecting silence)")
        self.hearing.texts = []  # Clear previous texts
        self.hearing.run_hearing()  # Records until silence threshold is reached
        
        # Resume vision processing
        self.resume_vision_processing()
        
        # Extract speaker embedding from ALL the recorded audio
        raw_audio = self.hearing.get_full_audio()
        speaker_embedding = None
        
        if raw_audio is not None:
            audio_duration = len(raw_audio) / 16000
            print(f"Audio captured: {audio_duration:.1f} seconds")
            
            if audio_duration >= 1.0:  # At least 1 second minimum to avoid errors
                # Use ALL the captured audio for embedding (not just first X seconds)
                speaker_embedding = self.extract_speaker_embedding(raw_audio)
                if speaker_embedding is not None:
                    print(f"✓ Voice enrollment successful using {audio_duration:.1f}s of audio")
                    return speaker_embedding
                else:
                    print("✗ Failed to extract speaker embedding")
                    self.speech.run_speech(text="Sorry, I couldn't process your voice. Let's try again.")
            else:
                print(f"⚠ Audio too short ({audio_duration:.1f}s), need at least 1 second")
                self.speech.run_speech(text="That was too short. Please speak the phrase clearly.")
        else:
            print("✗ No audio captured")
            self.speech.run_speech(text="I didn't hear anything. Let's try again.")
        
        return None
        
    def add_face_to_database(self, face_id, name):
        """Add the face and speaker to databases using pre-captured encodings."""
        print(f"\n=== Adding {name} to databases ===")
        
        try:
            # Check face encoding
            if self.captured_face_encoding is None:
                print("✗ No face encoding was captured earlier!")
                self.speech.run_speech(text="Sorry, I lost your face data. Let's try again.")
                return False
            
            print(f"Using pre-captured face encoding: {len(self.captured_face_encoding)} dimensions")
            
            # Add face to database
            print(f"Saving {name}'s face to database...")
            self.vision.face_db.save_face_to_db(name, self.captured_face_encoding)
            print(f"✓ Face saved! Database now has {len(self.vision.face_db.known_names)} faces")
            
            # NEW: Add speaker to database
            if self.captured_speaker_embedding is not None:
                print(f"Saving {name}'s voice to database...")
                self.speaker_db.add_speaker(name, self.captured_speaker_embedding)
                print(f"✓ Voice saved! Database now has {len(self.speaker_db.speaker_data)} speakers")
            else:
                print("⚠ No speaker embedding captured - only face was saved")
            
            self.speech.run_speech(text=f"Great! I'll remember your face and voice, {name}!")
            
            # Clear the captured data
            self.captured_face_crop = None
            self.captured_face_encoding = None
            self.captured_speaker_embedding = None
            self.registering_face_id = None
            
            return True
            
        except Exception as e:
            print(f"✗ Error adding to databases: {e}")
            import traceback
            traceback.print_exc()
            self.speech.run_speech(text="Sorry, something went wrong. Let's try again.")
            return False
    
    def get_and_confirm_name(self, max_name_attempts=3, max_confirm_attempts=3):
        """Get name from user and confirm it with gesture or voice. Returns (name, success)."""
        
        for name_attempt in range(max_name_attempts):
            if not self.demo_running:
                return None, False
            
            # Ask for name
            print(f"\n--- Name attempt {name_attempt+1}/{max_name_attempts} ---")
            name = self.ask_for_name()
            
            if not name:
                print(f"✗ Couldn't extract name (attempt {name_attempt+1}/{max_name_attempts})")
                if name_attempt < max_name_attempts - 1:
                    self.speech.run_speech(text="Sorry, I didn't catch that. Can you say your name again?")
                continue
            
            print(f"✓ Extracted name: {name}")

            # Resume vision processing
            self.resume_vision_processing()
            
            # Try to confirm the name multiple times
            for confirm_attempt in range(max_confirm_attempts):
                if not self.demo_running:
                    return None, False
                
                print(f"\n--- Confirmation attempt {confirm_attempt+1}/{max_confirm_attempts} for name '{name}' ---")
                
                confirmed = self.confirm_name(name)
                
                if confirmed is True:
                    # Confirmed (thumbs up or positive voice) - name is correct!
                    print(f"✓ Name '{name}' confirmed!")
                    return name, True
                    
                elif confirmed is False:
                    # Rejected (thumbs down or negative voice) - name is wrong, ask again
                    print(f"✗ Name '{name}' rejected, asking again...")
                    self.speech.run_speech(text="Okay, let me try again. What's your name?")
                    break  # Break out of confirm loop to ask for name again
                    
                else:
                    # Timeout - retry confirmation
                    print(f"⏱ Timeout on confirmation (attempt {confirm_attempt+1}/{max_confirm_attempts})")
                    if confirm_attempt < max_confirm_attempts - 1:
                        self.speech.run_speech(text=f"I didn't see a gesture. Is your name {name}? Thumbs up or down please.")
                    else:
                        # All confirmation attempts failed, ask for name again
                        print(f"✗ All confirmation attempts failed for '{name}'")
                        self.speech.run_speech(text="Let me ask again. What's your name?")
                        break
        
        # All attempts exhausted
        return None, False
    
    def run_demo(self):
        """Run the complete face registration demo."""
        print("\n" + "="*50)
        print("FACE & SPEAKER REGISTRATION DEMO")
        print("="*50)
        print("\nTIPS:")
        print("- Make sure your face is clearly visible to the camera")
        print("- Stay still while being detected")
        print("- The system needs to confirm you're unknown for 5 seconds")
        print("- Speak clearly when saying your name")
        print("- Use thumbs up/down gesture to confirm your name")
        print("- Press 'q' in the camera window to quit")
        print("="*50)
        
        try:
            # Start vision system
            print("\nStarting vision system...")
            self.vision.run_vision()
            
            print("✓ Vision system started")
            
            # Wait for camera to initialize and get frames
            print("Checking camera feed...")
            for i in range(15):  # Try for 3 seconds
                frame = self.vision.get_latest_frame()
                if frame is not None:
                    print(f"✓ Camera feed active after {(i+1)*0.2:.1f}s")
                    break
                print(f"Waiting for camera... {(i+1)*0.2:.1f}s", end='\r')
                time.sleep(0.2)
            else:
                print("\n⚠ No camera frame yet, but continuing...")
            
            # Start the display loop manually in a separate thread
            print("Starting display window...")
            display_thread = threading.Thread(target=self.vision._display_loop, daemon=True)
            display_thread.start()
            
            time.sleep(1)  # Extra buffer time
            
            print("\n✓ System ready! Show your face to the camera...")
            print("(The camera window will display - press 'q' there to quit)\n")
            
            # Step 1: Wait for unknown face (captures encoding during confirmation)
            face_id = self.wait_for_unknown_face()
            
            if not self.demo_running or face_id is None:
                print("Demo stopped or no face detected")
                return
            
            print(f"\n✓ Proceeding with face ID: {face_id}")
            
            # Steps 2-5: Get name and confirm with retries (also captures speaker embedding)
            name, success = self.get_and_confirm_name(max_name_attempts=3, max_confirm_attempts=3)
            
            if not success or not name:
                print("\n✗ Failed to get confirmed name after multiple attempts")
                self.speech.run_speech(text="Sorry, I'm having trouble. Let's try again later.")
                return
            
            # NEW STEP: Capture voice enrollment
            print(f"\n✓ Name confirmed: {name}")
            speaker_embedding = self.capture_voice_enrollment(name)
            
            if speaker_embedding is not None:
                self.captured_speaker_embedding = speaker_embedding
                print("✓ Voice enrollment captured")
            else:
                print("⚠ Voice enrollment failed, will only save face")
                # You can decide: continue anyway or retry
                # For now, we'll continue with just face
            
            # Step 6: Add to databases (uses pre-captured face and speaker encodings)
            if self.demo_running:
                success = self.add_face_to_database(face_id, name)
                
                if success:
                    print("\n" + "="*50)
                    print(f"✓✓✓ SUCCESS! {name} has been registered! ✓✓✓")
                    print("="*50)
                else:
                    print("\n" + "="*50)
                    print("✗✗✗ FAILED to register ✗✗✗")
                    print("="*50)
        
        except KeyboardInterrupt:
            print("\n\nDemo interrupted by user")
        
        except Exception as e:
            print(f"\n\nError in demo: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            print("\n=== Cleaning up ===")
            self.demo_running = False
            self.vision.stop_vision()
            self.vision.cleanup()
            print("Demo complete!")


if __name__ == "__main__":
    # Set pause_vision_during_stt=True for better speech-to-text performance
    # Set to False if you need continuous vision processing
    demo = FaceRegistrationDemo(pause_vision_during_stt=True)
    demo.run_demo()