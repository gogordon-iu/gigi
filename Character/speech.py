import librosa
IS_FFMPEG = False
try:
    import ffmpeg
    IS_FFMPEG = True
except:
    IS_FFMPEG = False

import numpy as np
import os
import time as sleep_time
from speechDefinitions import *
import threading
import json
import os
import time
import shutil
from characterDefinitions import IS_ROBOT, base_assets_path


SOUND_OPTION = "sounddevice"
if SOUND_OPTION == "pygame":
    from pygame import mixer, time
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1" 
elif SOUND_OPTION == "sounddevice":
    import sounddevice as sd
    import soundfile as sf

import torch, torchaudio
lanugage_speakers = {
    'en': ('v3_en', {
        'female': 'en_0',
        'male': 'en_1'}, OUTPUT_SAMPLE_RATE),
    'es': ('v3_es', 'es_2', OUTPUT_SAMPLE_RATE),
    'multi': ('multi_v2', 'lj', 8000)
}

MULTI = False

class Speech():

    def __init__(self, languages="en", activity=None, child=False, gender='female', verbose=False):
        self.activity = activity
        self.verbose = verbose
        self.child = child
        self.gender = gender
        print("Initializing speech ...")
        self.sample_rate = 0.1
        self.audio_objects = {}

        self.recorded_audio = {}
        self.keep_record = not IS_ROBOT #True
        self.set_activity(activity_name=activity)

        if os.path.exists(recorded_speech_filename):
            self.recorded_audio = json.load(open(recorded_speech_filename, "r"))
        else:
            self.save_recorded_audio()

        if SOUND_OPTION == "pygame":
            mixer.init()
        elif SOUND_OPTION == "sounddevice":
            speaker_device = self.get_usb_speaker()
            sd.default.device = (None, speaker_device)  # (input_device, output_device)


        # Download the model from TorchHub
        if IS_ROBOT: # No model
            self.model = None
            # self.model, self.symbols, self.audio_sample_rate, example_text, self.apply_tts = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts', language='en', speaker='lj_8khz')
            # self.device   = torch.device('cpu')   # keep it on CPU for Orange Pi
        else: # Large model
            self.languages = []
            if isinstance(languages, str):
                self.languages.append(languages)
            elif isinstance(languages, list):
                self.languages = languages
            
            if len(self.languages) == 1:
                self.model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models', 
                                                          model='silero_tts', 
                                                          language=self.languages[0], 
                                                          speaker=lanugage_speakers[self.languages[0]][0])
                if isinstance(lanugage_speakers[self.languages[0]][1], dict):
                    if self.gender in lanugage_speakers[self.languages[0]][1]:
                        self.speaker = lanugage_speakers[self.languages[0]][1][self.gender]
                    else:
                        self.speaker = lanugage_speakers[self.languages[0]][1].values()[0]
                else:
                    self.speaker = lanugage_speakers[self.languages[0]][1]
                self.wav_sr = lanugage_speakers[self.languages[0]][2]
            else:
                if MULTI:
                    self.model, example = torch.hub.load('snakers4/silero-models',
                                                        'silero_tts',
                                                        language='multi', # multilingual checkpoint
                                                        speaker=lanugage_speakers['multi'][0])
                    self.speaker = lanugage_speakers['multi'][1]
                    self.wav_sr = lanugage_speakers['multi'][2]
                else:   
                    self.models = []
                    self.speakers = []
                    self.wav_sr = OUTPUT_SAMPLE_RATE
                    for lang in self.languages:
                        model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models', 
                                                             model='silero_tts', 
                                                             language=lang, 
                                                             speaker=lanugage_speakers[lang][0])
                        self.models.append(model)
                        speaker = 'en_0'
                        if isinstance(lanugage_speakers[lang][1], dict):
                            if self.gender in lanugage_speakers[lang][1]:
                                speaker = lanugage_speakers[lang][1][gender]
                        else:
                            speaker = lanugage_speakers[lang][1]
                        self.speakers.append(speaker)
    
    def set_activity(self, activity_name):
        self.activity = activity_name
        if self.activity:
            self.activity_speech_path = base_assets_path + self.activity + "/speech/"
        else:
            self.activity_speech_path = recorded_speech_path
        if not os.path.exists(self.activity_speech_path):
            os.makedirs(self.activity_speech_path)
        if self.activity not in self.recorded_audio:
            self.recorded_audio[self.activity] = {}

    def save_recorded_audio(self):
        if not IS_ROBOT:
            if not os.path.exists(recorded_speech_path):
                os.makedirs(recorded_speech_path)
            json.dump(self.recorded_audio, open(recorded_speech_filename, "w+"))

    def save_audio_file(self, file, data, samplerate=OUTPUT_SAMPLE_RATE):
        sf.write(file, data, samplerate, subtype='PCM_16')
        
        if self.child and IS_FFMPEG:
            ffmpeg_path = r"C:/Users/gorengor/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
            (
                ffmpeg
                .input(file)
                .filter('asetrate', '48000*1.3348')
                .filter('aresample', 48000)
                .filter('atempo', 1/1.3348)
                # .filter('atempo', 1/1.3348)                
                .output('../Assets/recorded_speech/child.wav')
                .overwrite_output()
                .run(cmd=ffmpeg_path)
            )
            # Remove the original file if needed
            os.remove(file)   
            # Copy the converted file to the original name
            shutil.copy('../Assets/recorded_speech/child.wav', file)


    def get_usb_speaker(self):
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and "USB" in d["name"]:
                return i
        # No USB speaker, find another one
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0:
                return i
    
    def generate_speech_text(self, text=None, file=None):
        print("Generating speech ... ", text)
        # Synthesize speech
        if IS_ROBOT:
            return None

        if len(self.languages) == 1:
            audio = self.model.apply_tts(text=text, 
                                        speaker=self.speaker, 
                                        sample_rate=self.wav_sr)
        else:
            if MULTI:
                audio = self.model.apply_tts(texts=[text], 
                                            speakers=[self.speaker],
                                            sample_rate=self.wav_sr)[0]
            else:
                text_parts = text.split("#")
                num_parts = 0
                for i, part in enumerate(text_parts):
                    if len(part) == 0:
                        continue
                    part_lang = i % 2
                    if part_lang == 1:
                        rate="slow"
                    else:
                        rate="fast"
                    ssml = f"""
<speak>
<prosody pitch="low"><prosody rate="{rate}"> {part}</prosody></prosody>
</speak>
"""
                    audio_part = self.models[part_lang].apply_tts(
                        ssml_text=ssml, speaker=self.speakers[part_lang], 
                        sample_rate=self.wav_sr)
                    if num_parts == 0:
                        audio = audio_part
                    else:
                        audio = torch.cat((audio, audio_part), dim=0)
                        # # Ensure tensors are at least 2D before concatenation
                        # audio = torch.cat((audio.unsqueeze(0) if audio.dim() == 1 else audio, 
                        #                    audio_part.unsqueeze(0) if audio_part.dim() == 1 else audio_part), dim=1)
                    num_parts += 1

        wav = audio.numpy()
        # Increase the pitch of the audio
        # wav = librosa.effects.pitch_shift(wav, sr=self.wav_sr, n_steps=6)
        stereo_audio = np.column_stack((wav, wav))

        if self.keep_record:
            audio_file = self.activity_speech_path + generate_random_filename(extension="wav")
            # remove previous record if exists
            self.recorded_audio[self.activity] = {key: value for key, value in self.recorded_audio[self.activity].items() if value != text}
            self.recorded_audio[self.activity][audio_file] = text
            self.save_recorded_audio()
        else:
            audio_file = "../temp/output.wav"
        env_file = audio_file.replace(".wav", ".npy")
        if SOUND_OPTION == "sounddevice":
            if len(stereo_audio.shape) > 1:
                stereo_audio = stereo_audio[:,0]
            if self.wav_sr != OUTPUT_SAMPLE_RATE:
                stereo_audio = librosa.resample(stereo_audio, orig_sr=self.wav_sr, target_sr=OUTPUT_SAMPLE_RATE)
            self.save_audio_file(audio_file, stereo_audio, samplerate=OUTPUT_SAMPLE_RATE)
            envelope = self.get_envelope(audio_file, y=wav, sr=OUTPUT_SAMPLE_RATE)
            # envelope = self.get_envelope(audio_file, y=stereo_audio, sr=OUTPUT_SAMPLE_RATE)
            if self.keep_record:
                np.save(env_file, envelope)

            self.audio_objects[audio_file] = {
                "data": stereo_audio, 
                "samplerate": OUTPUT_SAMPLE_RATE,
                "envelope": envelope
            }
        if SOUND_OPTION == "pygame":
            sf.write(file=audio_file, data=stereo_audio, samplerate=OUTPUT_SAMPLE_RATE)
            envelope = self.get_envelope(audio_file)
            if self.keep_record:
                np.save(env_file, envelope)
            self.audio_objects[audio_file] = {
                "sound": mixer.Sound(audio_file),
                "envelope": envelope
            }
        return audio_file

    def generate_speech_file(self, file=None):
        if not os.path.exists(file):
            # check in base audio folder
            file = self.activity_speech_path + file.split('/')[-1]
        if not os.path.exists(file):
            # check in base audio folder
            file = audio_path + file.split('/')[-1]
        if not os.path.exists(file):
            print(f"ERROR: audio file {file.split('/')[-1]} not found!")
            return None, None, None, None
        data, samplerate = sf.read(file)
        if self.verbose:
            print("DEBUG: samplerate", samplerate)
        # first change to mono (not stereo)
        if len(data.shape) > 1:
            data = data[:,0]
        # then if required, resample
        if samplerate != OUTPUT_SAMPLE_RATE:
            data = librosa.resample(data, orig_sr=samplerate, target_sr=OUTPUT_SAMPLE_RATE)
            # Save the resampled audio to a new file
            self.save_audio_file(file, data, samplerate=OUTPUT_SAMPLE_RATE)
        envelope = self.get_envelope(file, y=data, sr=samplerate)

        if self.keep_record:
            audio_file = self.activity_speech_path + file.split('/')[-1]
            shutil.copy(file, audio_file)
            env_file = audio_file.replace(".wav", ".npy")
            np.save(env_file, envelope)
            # remove previous record if exists
            self.recorded_audio[self.activity] = {key: value for key, value in self.recorded_audio[self.activity].items() if value != file.split('/')[-1]}
            self.recorded_audio[self.activity][audio_file] = file.split('/')[-1]
            self.save_recorded_audio()
        else:
            audio_file = file
        return audio_file, data, samplerate, envelope

    def update_audio_objects(self, file=None, text=None):
        env_file = None
        found = False
        if text is not None:
            # check if speech is already recorded
            pre_audio_file = [key for key, value in self.recorded_audio[self.activity].items() if value == text]
            if len(pre_audio_file) > 0:
                file = pre_audio_file[0]
                if os.path.exists(file):
                    env_file = file.replace(".wav", ".npy")
                    print("Found record: ", file)
                    found = True
        elif file is not None:
            # check if speech is already recorded
            pre_audio_file = [key for key, value in self.recorded_audio[self.activity].items() if value == file]
            for file in pre_audio_file:
                if os.path.exists(file):
                    env_file = file.replace(".wav", ".npy")
                    print("Found record: ", file)
                    found = True
                    break

        
        if text is not None:
            if file is None:
                audio_file = self.generate_speech_text(text=text)
            else:
                audio_file = file
                if SOUND_OPTION == "pygame":
                    if env_file is not None:
                        envelope = np.load(env_file)
                    else:
                        envelope = self.get_envelope(audio_file)
                    self.audio_objects[audio_file] = {
                        "sound": mixer.Sound(audio_file),
                        "envelope": envelope
                    }
                elif SOUND_OPTION == "sounddevice":
                    loaded_audio = False
                    if os.path.exists(audio_file):
                        try:
                            data, samplerate = sf.read(audio_file)
                            print("Loading speech ...")
                            loaded_audio = True
                        except Exception as e:
                            print("Error reading audio file:", e)
                            os.remove(audio_file)
                            self.update_audio_objects(text=text, file=None)
                    if loaded_audio:
                        # first change to mono (not stereo)
                        if len(data.shape) > 1:
                            data = data[:,0]
                        # then if required, resample
                        if samplerate != OUTPUT_SAMPLE_RATE:
                            data = librosa.resample(data, orig_sr=samplerate, target_sr=OUTPUT_SAMPLE_RATE)
                            # Save the resampled audio to a new file
                            self.save_audio_file(audio_file, data, samplerate=OUTPUT_SAMPLE_RATE)

                        if env_file is not None:
                            if os.path.exists(env_file):
                                envelope = np.load(env_file)
                            else:
                                envelope = self.get_envelope(audio_file, y=data, sr=samplerate)
                                if self.keep_record:
                                    np.save(env_file, envelope)
                        else:
                            envelope = self.get_envelope(audio_file, y=data, sr=samplerate)
                        self.audio_objects[audio_file] = {
                            "data": data, 
                            "samplerate": samplerate,
                            "envelope": envelope
                        }
                    else:
                        audio_file = self.generate_speech_text(text=text)
        elif file is not None:
            if not found:
                if SOUND_OPTION == "sounddevice":
                    audio_file, data, samplerate, envelope = self.generate_speech_file(file=file)
            else:
                audio_file = file
                if SOUND_OPTION == "sounddevice":
                    data, samplerate = sf.read(file)
                       
                if os.path.exists(env_file):
                    envelope = np.load(env_file)
                else:
                    envelope = self.get_envelope(file, y=data, sr=samplerate)
                    if self.keep_record:
                        np.save(env_file, envelope)
            self.audio_objects[audio_file] = {
                "data": data, 
                "samplerate": samplerate,
                "envelope": envelope
                }


        return audio_file
    
    def get_envelope(self, file, max_length=-1, y=None, sr=None):
        if y is None and sr is None:
            y, sr = librosa.load(file, sr=None)
        if max_length > 0:
            y = y[:sr*max_length]
        envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=int(sr * self.sample_rate))
        envelope = envelope / np.max(envelope)

        envelope = np.minimum(envelope * 4, 1.0)
        return envelope

    # FOR ROBOT ONLY==============================
    # def get_envelope(self, file, max_length=-1, y=None, sr=None):
    #     y, sr = librosa.load(file, sr=None)
    #     print("DEBUG: y", y.shape)
    #     if max_length > 0:
    #         y = y[:sr*max_length]
    #     print("DEBUG: y", y.shape)
    #     y = y.mean(axis=-1) if y.ndim > 1 else y
    #     print("DEBUG: y", y.shape)

    #     win = int(0.02 * sr)                 # 20 ms window
    #     env = np.convolve(np.abs(y), np.ones(win), 'valid') / win
    #     step = int(0.02 * sr)                # stride to 50 fps
    #     env = env[::step]

    #     env /= env.max()
    #     env = np.minimum(env*4, 1.0)
    #     print("DEBUG: env", env)
    #     print("DEBUG: env", env.shape)
    #     return env


    
    def generate_audio(self, text=None, file=None, stop_event=None, stop_condition=None):
        file = self.update_audio_objects(text=text, file=file)

        if SOUND_OPTION == "pygame":
            sound = self.audio_objects[file]["sound"]
            with self.pygame_lock:
                sound.play()

                while mixer.get_busy():
                    time.Clock().tick(10)
                    if stop_event is not None:
                        if stop_event.is_set():
                            break
                sound.stop()
                if AUDIO_DELAY:
                    sleep_time.sleep(AUDIO_DELAY)
                
                if stop_condition is not None:
                    if "audio" in stop_condition:
                        stop_event.set()
        elif SOUND_OPTION == "sounddevice":
            # Define a callback for when playback finishes
            def on_finished():
                print("Audio finished!")

            # Play audio
            sd.play(self.audio_objects[file]["data"], samplerate=self.audio_objects[file]["samplerate"])
            sd.wait()  # Wait until playback finishes
            on_finished()

    def audio_thread(self, text=None, file=None):
        stop_event = threading.Event()
        t = threading.Thread(target=self.generate_audio, args=(text, file, stop_event, None))
        return t
    
    def run_speech(self, text=None, file=None):
        audio_thread = self.audio_thread(text, file)
        audio_thread.start()
        audio_thread.join()

if __name__ == "__main__":
    speech = Speech(languages=["en", "es"], child=True, verbose=True)
    speech.set_activity("test_speech")
    # speech.run_speech(text="ten we're going to build a Ferris wheel. Or in Spanish, we say. #la noria.# Do you know what a Ferris wheel is? Tell your friends.")
    # speech.run_speech(text="¡Hola, mundo dos!")
    speech.run_speech(text="We are going to build a Ferris wheel. Four.")
    # speech.run_speech(file="../Assets/teacher/laugh.wav")
    # speech.run_speech(file="../Assets/audio/demo_01_greetings.wav")
    # speech.run_speech(text="hi")
