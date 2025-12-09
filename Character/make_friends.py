import time
import re
import threading
from newvision import Vision
from speech import Speech
from hearing_new2 import Hearing
from conversation import Conversation

class FaceRegistrationDemo:
    def __init__(self, pause_vision_during_stt=True):
        # Initialize components
        self.vision = Vision(None, auto_start=False)
        self.vision.is_robot = False
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
        
        # Demo parameters
        self.unknown_threshold = 5.0  # seconds to confirm it's a new face
        self.pause_vision_during_stt = pause_vision_during_stt  # Performance optimization
        
        # Display control - NOT NEEDED, Vision class handles it
        self.demo_running = True
    
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
            # Smal):l delay to ensure processing stops
            time.sleep(0.2)
    
    def resume_vision_processing(self):
        """Resume vision processing after pause."""
        print("▶ Resuming vision processing...")
        if self.pause_vision_during_stt:
            self.vision.set_processing_flags({
                'face_detection': 8.0,
                'face_recognition': 8.0,
                'emotion': 0,
                'gesture': 8.0
            })
            # Small delay to let processing restart
            time.sleep(0.2)

    def wait_for_unknown_face(self):
        """Wait until we detect an unknown face for X seconds and capture the best crop during confirmation."""
        print("\n=== Waiting for unknown face ===")
        print("Looking at camera to detect faces...")
        
        unknown_start_time = None
        unknown_face_id = None
        last_status = None
        best_face_crop = None
        best_face_box = None
        best_crop_size = 0
        
        while self.demo_running:
            # Get data directly from face cache for more accurate info
            all_faces = self.vision.face_cache.get_all_faces()
            data = self.vision.get_last_data()
            
            # Debug: Show what we're seeing
            current_status = f"Faces detected: {len(all_faces)}"
            if current_status != last_status:
                print(f"\n{current_status}")
                last_status = current_status
            
            if all_faces:
                for face_id, face_info in all_faces.items():
                    name = face_info.get('name', 'Unknown')
                    print(f"  Face {face_id}: name='{name}', recognition_attempted={face_info.get('recognition_attempted', False)}", end='\r')
                    
                    # Check if face is Unknown OR matches face_xxxx pattern
                    # A face is "unknown" if:
                    # 1. Name is explicitly "Unknown", OR
                    # 2. Name matches pattern "face_xxxx" (where xxxx is any 4-digit number), OR
                    # 3. Recognition was attempted and name is still "Recognizing..."
                    is_face_pattern = re.match(r'^face_\d{4}$', name) is not None
                    is_unknown = (name == 'Unknown' or
                                is_face_pattern or
                                (name == 'Recognizing...' and face_info.get('recognition_attempted', False)))
                    
                    if is_unknown:
                        if unknown_start_time is None:
                            unknown_start_time = time.time()
                            unknown_face_id = face_id
                            print(f"\n\nUnknown face detected (ID: {face_id}, name: '{name}'), confirming...")
                        
                        elapsed = time.time() - unknown_start_time
                        
                        # CAPTURE FACE CROPS CONTINUOUSLY DURING CONFIRMATION
                        # Keep the best (largest) crop
                        import cv2
                        try:
                            frame = self.vision.get_latest_frame()
                            if frame is not None:
                                face_data = self.vision.face_cache.get_face_data(face_id)
                                if face_data and 'box' in face_data:
                                    x_min, y_min, x_max, y_max = face_data['box']
                                    face_crop = frame[y_min:y_max, x_min:x_max]
                                    
                                    if face_crop.size > 0:
                                        # Calculate crop quality (based on size)
                                        crop_area = face_crop.shape[0] * face_crop.shape[1]
                                        
                                        # Keep the largest crop (usually means face is closer/clearer)
                                        if crop_area > best_crop_size:
                                            best_face_crop = face_crop.copy()
                                            best_face_box = (x_min, y_min, x_max, y_max)
                                            best_crop_size = crop_area
                                            print(f"\n📸 Captured better crop: {face_crop.shape} (area: {crop_area})", end='')
                        except Exception as e:
                            pass  # Continue even if crop fails
                        
                        print(f"\n  Confirming unknown face... {elapsed:.1f}s / {self.unknown_threshold}s", end='\r')
                        
                        if elapsed >= self.unknown_threshold:
                            print(f"\n✓ Confirmed unknown face after {elapsed:.1f} seconds")
                            
                            # Store the best captured crop
                            if best_face_crop is not None:
                                self.captured_face_crop = best_face_crop
                                self.captured_face_box = best_face_box
                                print(f"✓ Best face crop stored: {best_face_crop.shape} (area: {best_crop_size})")
                                return unknown_face_id
                            else:
                                print("✗ No valid face crop captured during confirmation, resetting...")
                                unknown_start_time = None
                                unknown_face_id = None
                                best_crop_size = 0
                                continue
                    else:
                        # Known face detected
                        if unknown_start_time is not None:
                            print(f"\n\nFace recognized as '{name}', resetting...")
                        unknown_start_time = None
                        unknown_face_id = None
                        best_face_crop = None
                        best_face_box = None
                        best_crop_size = 0
            else:
                # No face detected
                if unknown_start_time is not None:
                    print("\n\nNo face detected, resetting...")
                unknown_start_time = None
                unknown_face_id = None
                best_face_crop = None
                best_face_box = None
                best_crop_size = 0
            
            time.sleep(0.2)
        
        return None
    
    def ask_for_name(self):
        """Ask for the person's name and get response."""
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
        
        # Give some time for hearing to capture the response
        time.sleep(3)
        
        # Resume vision processing
        self.resume_vision_processing()
        
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
    
    def add_face_to_database(self, face_id, name):
        """Add the face to the database."""
        print(f"\n=== Adding {name} to database ===")
        
        import cv2
        import face_recognition
        
        try:
            # Get current frame with the face
            frame = self.vision.get_latest_frame()
            if frame is None:
                print("✗ No frame available")
                self.speech.run_speech(text="Sorry, I can't see you right now. Let's try again.")
                return False
            
            # Get face data from cache - face_id is an integer
            face_data = self.vision.face_cache.get_face_data(face_id)
            
            if not face_data or 'box' not in face_data:
                print(f"✗ Face data not found in cache for ID: {face_id}")
                print(f"Available faces: {list(self.vision.face_cache.faces.keys())}")
                self.speech.run_speech(text="Sorry, I lost track of your face. Let's try again.")
                return False
            
            # Extract face crop using the bounding box
            x_min, y_min, x_max, y_max = face_data['box']
            face_crop = frame[y_min:y_max, x_min:x_max]
            
            if face_crop.size == 0:
                print("✗ Invalid face crop")
                self.speech.run_speech(text="Sorry, I couldn't capture your face properly. Let's try again.")
                return False
            
            print(f"Face crop size: {face_crop.shape}")
            
            # Resize and convert for face_recognition
            small_face = cv2.resize(face_crop, (0, 0), fx=0.5, fy=0.5)
            face_crop_rgb = cv2.cvtColor(small_face, cv2.COLOR_BGR2RGB)
            
            # Extract face encoding
            print("Extracting face encoding...")
            face_encodings = face_recognition.face_encodings(face_crop_rgb)
            
            if not face_encodings:
                print("✗ Could not extract face encoding")
                self.speech.run_speech(text="Sorry, I couldn't process your face. Let's try again.")
                return False
            
            print(f"Face encoding extracted: {len(face_encodings[0])} dimensions")
            
            # Add to database
            print(f"Saving {name} to database...")
            self.vision.face_db.save_face_to_db(name, face_encodings[0])
            
            print(f"✓ Successfully added {name} to database!")
            print(f"Database now has {len(self.vision.face_db.known_names)} faces")
            
            self.speech.run_speech(text=f"Great! I'll remember you, {name}!")
            return True
            
        except Exception as e:
            print(f"✗ Error adding face to database: {e}")
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
        
        try:
            # Start vision system (non-blocking since is_robot=False will handle display)
            print("\nStarting vision system...")
            
            # Start vision in a separate thread so we can continue
            vision_thread = threading.Thread(target=self.vision.run_vision, daemon=True)
            vision_thread.start()
            
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
            
            time.sleep(1)  # Extra buffer time
            
            print("\n✓ System ready! Show your face to the camera...")
            print("(The camera window will display - press 'q' there to quit)\n")
            
            # Step 1: Wait for unknown face
            face_id = self.wait_for_unknown_face()
            
            if not self.demo_running or face_id is None:
                print("Demo stopped or no face detected")
                return
            
            print(f"\n✓ Proceeding with face ID: {face_id}")
            
            # Steps 2-5: Get name and confirm with retries
            name, success = self.get_and_confirm_name(max_name_attempts=3, max_confirm_attempts=3)
            
            if not success or not name:
                print("\n✗ Failed to get confirmed name after multiple attempts")
                self.speech.run_speech(text="Sorry, I'm having trouble. Let's try again later.")
                return
            
            # Step 6: Add to database
            if self.demo_running:
                success = self.add_face_to_database(face_id, name)
                
                if success:
                    print("\n" + "="*50)
                    print(f"✓✓✓ SUCCESS! {name} has been registered! ✓✓✓")
                    print("="*50)
                else:
                    print("\n" + "="*50)
                    print("✗✗✗ FAILED to register face ✗✗✗")
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