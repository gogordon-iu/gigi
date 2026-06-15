from face import Face
from speech import Speech
import threading


class Viseme():
    def __init__(self, face=None, speech=None, character_name="fuzzy"):
        print("Initializing viseme ...")
        if face is None:
            self.face = Face(character=character_name, full_screen=True)
        else:
            self.face = face
        
        if speech is None:
            self.speech = Speech()
        else:
            self.speech = speech
            
        self.sync_offset = 0.0


    def set_viseme(self, envelope_):
        mouth_sequences = self.face.character["part_sequence"]["Mouth"]
        for seq in mouth_sequences:
            if "talk" == seq[0]:
                talk_length = len(seq[1])
                break
        talk_sequence =  {
            "Mouth": ("talk", [str(min(talk_length, int(env * talk_length)+1)) for env in envelope_])
        }
        return talk_sequence

    def generate_viseme_sequence(self, text=None, file=None):
        file = self.speech.update_audio_objects(file=file, text=text)
        if file:
            envelope = self.speech.audio_objects[file]["envelope"]
            talk_sequence = self.set_viseme(envelope)
            return talk_sequence
        else:
            print("DEBUG: No audio file or text provided.")
            return None 

    def generate_viseme(self, text=None, file=None, stop_event=None, stop_condition=None, start_time=None):
        talk_sequence = self.generate_viseme_sequence(text=text, file=file)
        self.face.generate_face(parts_selected=talk_sequence, stop_event=stop_event, stop_condition="face", delay=self.speech.sample_rate, start_time=start_time)

    def run_viseme(self, text=None, file=None):
        import time
        if hasattr(self, 'character') and self.character:
            if text:
                if not hasattr(self.character, 'activity_log'):
                    self.character.activity_log = []
                if not self.character.activity_log or self.character.activity_log[-1].get('text') != text:
                    self.character.activity_log.append({
                        "speaker": "Gigi",
                        "text": text,
                        "timestamp": time.time()
                    })
            elif file:
                if not hasattr(self.character, 'activity_log'):
                    self.character.activity_log = []
                self.character.activity_log.append({
                    "speaker": "Gigi",
                    "text": f"[Plays audio file: {file}]",
                    "timestamp": time.time()
                })

        if text and hasattr(self, 'character') and self.character:
            import re
            matched_name = None
            for name in self.character.egocentric_db.keys():
                if re.search(r'\b' + re.escape(name) + r'\b', text, re.IGNORECASE):
                    matched_name = name
                    break
            if matched_name:
                print(f"[Gaze Redirection] Matched '{matched_name}' in viseme text: '{text}'. Redirecting gaze.")
                self.character.lookat_person(matched_name)

        # 1. Update/generate the audio object synchronously in the main thread.
        # This resolves all race conditions when calling update_audio_objects from multiple threads.
        actual_file = self.speech.update_audio_objects(file=file, text=text)
        if not actual_file:
            print("ERROR: Could not load/generate speech audio.")
            return

        # 2. Get the envelope and set the viseme sequence
        envelope = self.speech.audio_objects[actual_file]["envelope"]
        talk_sequence = self.set_viseme(envelope)

        # 3. Coordinate audio playback and viseme rendering using a shared start time container
        start_time_container = [None]
        stop_event = threading.Event()

        # Start the playback thread
        speech_thread = threading.Thread(
            target=self.speech.play_audio, 
            args=(actual_file, stop_event, start_time_container, "audio")
        )
        speech_thread.start()

        # Wait until the audio thread actually begins playback
        while start_time_container[0] is None:
            time.sleep(0.001)

        # 4. Render the viseme sequence synchronized to the start time
        start_time = start_time_container[0]
        
        self.face.generate_face(
            parts_selected=talk_sequence, 
            stop_event=stop_event, 
            stop_condition="face", 
            delay=self.speech.sample_rate,
            start_time=start_time - self.sync_offset
        )

        speech_thread.join()

if __name__ == "__main__":
    viseme = Viseme()
    viseme.speech.set_activity(activity_name="wakeup")
    # viseme.run_viseme(file="Assets/audio/demo_01_greetings.wav")
    # viseme.run_viseme(text="Hi my name is gigi. This is test number three.")
    # viseme.generate_viseme_sequence(text="It's me again, Gigi.")
    viseme.run_viseme(text="It's me again, Gigi.")