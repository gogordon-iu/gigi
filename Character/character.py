from characterDefinitions import *
from faceDefinitions import *
if HAS_FACE:
    from face import Face
if HAS_SPEECH:
    from speech import Speech
if HAS_HEARING:
    from hearing import Hearing
if HAS_VISEME:
    from viseme import Viseme
if HAS_VISION:
    from vision import Vision
if HAS_MOVEMENT:
    from movement import Movement
if HAS_CONVERSATION:
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
            self.face = Face(character=character_name, full_screen=full_screen)
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
            except:
                self.movement = None
        else:
            self.movement = None

        if HAS_CONVERSATION:
            self.conv = Conversation()
        else:
            self.conv = None

        self.lookat_calibration = None
        if HAS_FACE and HAS_MOVEMENT and HAS_VISION:
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
        if viseme_data and HAS_SPEECH:
            speech_thread = self.speech.audio_thread(file=viseme_data['file'], text=viseme_data['text'])
            speech_thread.start()
        elif audio_data and HAS_SPEECH:
            speech_thread = self.speech.audio_thread(file=audio_data['file'], text=audio_data['text'])
            speech_thread.start()
        if movement_data and HAS_MOVEMENT:
            movement_thread = self.movement.movement_thread(motor_data=movement_data)
            movement_thread.start()

        # Priority in displaying on screen: video, image, text, face, viseme
        if (image_data or video_data or caption_data) and HAS_FACE:
            if video_data:
                self.face.display_video_file(filename=video_data['filename'])
            elif image_data:
                self.face.display_image_file(filename=image_data['filename'])
            elif caption_data:
                self.face.display_text(text=caption_data['caption'])
        elif HAS_FACE:
            self.face.display_image_file(filename=None)
            face_parts = []
            if face_data and HAS_FACE:
                if 'parts' in face_data:
                    face_parts.append([0.5, face_data['parts']])
                    # self.face.generate_face(parts_selected=face_data['parts'])
                elif 'sequence' in face_data:
                    face_parts.append([0.5, basic_sequences[face_data['sequence']]])
                    # self.face.run_sequence(face_sequence_name=face_data['sequence'])
            if viseme_data and HAS_VISEME:
                face_parts.append([self.speech.sample_rate,
                                   self.viseme.generate_viseme_sequence(file=viseme_data['file'], text=viseme_data['text'])])
                # self.viseme.generate_viseme(file=viseme_data['file'], text=viseme_data['text'])
            if len(face_parts) > 0:
                face_sequence, min_delay = self.face.combine_seuqences(sequences=face_parts)
                self.face.generate_face(parts_selected=face_sequence, stop_condition="face", delay=min_delay)

        if speech_thread:
            speech_thread.join()
        if movement_thread:
            movement_thread.join()

    def stop_character(self):
        if self.vision:
            if self.vision.stop_event:
                self.vision.stop_vision()

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

    def listen_backchannel(self):
        if self.hearing and self.face:
            stop_event = threading.Event()
            hearing_thread = self.hearing.hearing_thread(stop_event=stop_event)
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

    def lookfor_backchannel(self, what=None):
        if self.vision and self.face:
            stop_event = threading.Event()
            vision_thread = self.vision.vision_thread(stop_event=stop_event, what=what)
            vision_thread.start()
            while not stop_event.is_set():
                self.face.generate_face(parts_selected=basic_sequences["blink"], stop_event=stop_event)
            vision_thread.join()

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
        if self.vision and self.face and self.movement:
            self.vision.look_and_stop(what=what, timeout=1)
            if self.lookat_calibration:     # if calibrated, look at something
                print("DEBUG: ", what, self.vision.found)                
                if len(self.vision.found[what]) > 0:
                    self.vision.stop_vision()
                    offset = next(iter(self.vision.found[what].values()))["offset"][0]     # the x-offset of the first face
                    head_coor = self.lookat_coordinate(offset=offset)
                    self.lookat_behavior(target_coor=head_coor)
                    return True
                else:   # did not see a face
                    if timeout < 0:
                        return False
                    else:       # select a random side a look for that
                        head_coor = random.choice([1, 0, -1]) * FOLLOW_TORSO_OFFSET * 1.01
                        self.lookat_behavior(target_coor=head_coor)
                        duration = time.time() - start_time
                        remaining_timeout = timeout - duration
                        self.lookat_something(what=what, timeout=remaining_timeout)
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
        if self.viseme and self.conv:
            agent_text = "What do you want to talk about"
            for i in range(2):
                print("Agent: ", agent_text)
                self.viseme.run_viseme(text=agent_text)
                self.listen_backchannel()
                user_text = self.hearing.texts[-1]
                print("User: ", user_text)
                self.conv.response(input_text=user_text)
                agent_text = self.conv.text[-1]
        


if __name__ == "__main__":
    fuzzy = Character()
    # fuzzy.conversational_turn(file="Assets/audio/demo_01_greetings.wav")
    # fuzzy.lookfor_backchannel()
    # fuzzy.full_conversation()
    # fuzzy.listen_backchannel()
    fuzzy.movement.home_position()
    fuzzy.lookat_something(timeout=10)
    fuzzy.lookat_something(timeout=10)
    fuzzy.lookat_something(timeout=10)

