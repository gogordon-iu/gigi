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

    def generate_viseme(self, text=None, file=None, stop_event=None, stop_condition=None):
        talk_sequence = self.generate_viseme_sequence(text=text, file=file)
        self.face.generate_face(parts_selected=talk_sequence, stop_event=stop_event, stop_condition="face", delay=self.speech.sample_rate)

    def run_viseme(self, text=None, file=None):
        speech_thread = self.speech.audio_thread(file=file, text=text)
        speech_thread.start()
        self.generate_viseme(file=file, text=text)
        speech_thread.join()

if __name__ == "__main__":
    viseme = Viseme()
    # viseme.run_viseme(file="Assets/audio/demo_01_greetings.wav")
    # viseme.run_viseme(text="Hi my name is gigi. This is test number three.")
    viseme.generate_viseme_sequence(text="Hi my name is gigi. This is test number three.")