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
        else:
            self.conversation = None

        self.lookat_calibration = None
        if self.face and self.movement and self.vision:
            if exists(CHARACTER_FOLDER + "lookat_calibrated.json"):
                self.lookat_calibration = json.load(open(CHARACTER_FOLDER + "lookat_calibrated.json"))
                # keys = head position (-1.0, 1.0)
                # values = detected face offset (-1.0, 1.0)
        
        self.set_activity(activity_name=activity)
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

    def lookat_coordinate(self, offset=0.0):
        if self.lookat_calibration:
            vision_coor = np.array([float(i[0]) for i in list(self.lookat_calibration.values())])
            motor_coor = np.array([float(i) for i in list(self.lookat_calibration.keys())])            

            # First, calculate the torso-vision transformation
            motor_y = self.movement.calc_normalized_angle(motor="torso")
            rbf_interpolator = Rbf(motor_coor, vision_coor, smooth=0.05)
            motor_x = rbf_interpolator(motor_y)

            # Calculate the vision part, based on vision, what should the motor be
            # But subtrack the torso-based vision
            vision_x = offset + motor_x
            rbf_interpolator = Rbf(vision_coor, motor_coor, smooth=0.05)
            vision_y = rbf_interpolator(vision_x)
            vision_y = np.clip(vision_y, -0.9, 0.9)

            return vision_y
        return None

    def listen_backchannel(self, timeout=15):
        if self.hearing and self.face:
            stop_event = threading.Event()
            threading.Timer(timeout, stop_event.set).start()
            hearing_thread = self.hearing.hearing_thread(stop_event=stop_event)
            hearing_thread.start()
            while not stop_event.is_set():
                self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
            hearing_thread.join()

    def listen_fluid(self, timeout=30, n_transcripts=2, check_callback=None):
        if self.hearing and self.face:
            stop_event = threading.Event()
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
            
            while not stop_event.is_set():
                self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
            
            hearing_thread.join()

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
        side = "left" if target_coor > 0 else "right"
        if np.abs(target_coor) > FOLLOW_EYES_OFFSET:
            # move eyes, to show things have changed
            self.face.run_sequence(face_sequence_name=f"look_{side}")
            if np.abs(target_coor) > FOLLOW_NECK_OFFSET:
                # move the head in the direction of the face
                neck_seq = self.movement.smooth_sequence(motors_={"neck": target_coor}, duration=NECK_FOLLOW_DURATION)
                self.movement.move_sequence(motor_seq=neck_seq)
                if np.abs(target_coor) > FOLLOW_TORSO_OFFSET:
                    # move the torso
                    # return the head, since the body is now facing the face, so the head can be straight
                    torso_seq = self.movement.smooth_sequence(motors_={"torso": target_coor, "neck": 0.0}, duration=TORSO_FOLLOW_DURATION)
                    self.movement.move_sequence(motor_seq=torso_seq)
            # return the eyes, since we don't have fluid continuous eyes position.
            self.face.run_sequence(face_sequence_name="idle")

    def lookat_something(self, what="face", timeout=-1):
        # timeout - how long (seconds) to look for a face if one is not found
        start_time = time.time()
        if self.vision:            
            if self.lookat_calibration:     # if calibrated, look at something
                self.vision.look_and_stop(what=what, timeout=1)
                print("DEBUG: ", what, self.vision.found)                
                if len(self.vision.found[what]) > 0:
                    self.vision.stop_vision()
                    offset = next(iter(self.vision.found[what].values()))["offset"][0]     # the x-offset of the first face
                    head_coor = self.lookat_coordinate(offset=offset)
                    # DEBUG
                    self.lookat_behavior(target_coor=head_coor)
                    print("Found something!")
                    return True
                else:   # did not see a face
                    if timeout < 0:
                        print("Timed out")
                        return False
                    else:       # select a random side a look for that
                        head_coor = random.choice([1, 0, -1]) * FOLLOW_TORSO_OFFSET * 1.01
                        # DEBUG
                        self.lookat_behavior(target_coor=head_coor)
                        duration = time.time() - start_time
                        remaining_timeout = timeout - duration
                        print("Looking again ...")
                        return self.lookat_something(what=what, timeout=remaining_timeout)
            else:                           # if not calibrated, just report if found something
                self.vision.look_and_stop(what=what, timeout=timeout)
                return len(self.vision.found[what]) > 0
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

