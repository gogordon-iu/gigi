
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
import sys
import platform


SOUND_OPTION = "pygame"
APLAY_DEVICE = "plughw:1,0"  # ALSA device for OrangePi DP speakers
import soundfile as sf
if SOUND_OPTION == "pygame":
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
    if not IS_ROBOT:
        from pygame import mixer, time
    else:
        import subprocess as _subprocess
elif SOUND_OPTION == "sounddevice":
    import sounddevice as sd

TTS_MODEL = "nix"

# eSpeak path configuration based on platform
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    ESPEAK_PATH = r"C:/Program Files/eSpeak NG/espeak-ng.exe"
    ESPEAK_LIBRARY = r"C:/Program Files/eSpeak NG/libespeak-ng.dll"
else:
    # Linux/Unix paths
    ESPEAK_PATH = "/usr/bin/espeak-ng"  # or "/usr/bin/espeak"
    ESPEAK_LIBRARY = None  # Not needed on Linux

if TTS_MODEL == "nix":
    sys.path.append('../Resources')

    # Configure phonemizer to use eSpeak-NG
    if IS_WINDOWS:
        os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = ESPEAK_LIBRARY
    os.environ['PHONEMIZER_ESPEAK_PATH'] = ESPEAK_PATH

    from nix.models.TTS import NixTTSInference
    from nix.tokenizers.tokenizer_en import NixTokenizerEN
    TTS_SAMPLE_RATE = 22050

elif TTS_MODEL == "silero":
    import torch
    TTS_SAMPLE_RATE = 48000


lanugage_speakers = {
    'en': ('v3_en', {
        'female': 'en_0',
        'male': 'en_1'}, TTS_SAMPLE_RATE),
    'es': ('v3_es', 'es_1', TTS_SAMPLE_RATE),
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
        self.keep_record = True
        self.set_activity(activity_name=activity)

        if os.path.exists(recorded_speech_filename):
            self.recorded_audio = json.load(open(recorded_speech_filename, "r"))
        else:
            self.save_recorded_audio()

        self.speaker_sample_rate = TTS_SAMPLE_RATE
        if SOUND_OPTION == "pygame":
            if IS_ROBOT:
                self.speaker_sample_rate = 48000
            else:
                mixer.init(frequency=self.speaker_sample_rate)
            self.pygame_lock = threading.Lock()  # unused on robot but kept for consistency
        elif SOUND_OPTION == "sounddevice":
            speaker_device, self.speaker_sample_rate = self.get_usb_speaker()
            sd.default.device = (None, speaker_device)  # (input_device, output_device)


        # Download the model from TorchHub
        self.languages = []
        if isinstance(languages, str):
            self.languages.append(languages)
        elif isinstance(languages, list):
            self.languages = languages
        
        if len(self.languages) == 1:
            if TTS_MODEL == "silero" and not IS_ROBOT:
                self.model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models', 
                                                        model='silero_tts', 
                                                        language=self.languages[0], 
                                                        speaker=lanugage_speakers[self.languages[0]][0])
            elif TTS_MODEL == "nix":
                self.model = NixTTSInference(model_dir="../Resources/nix/models/")
            else:
                self.model = None

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
                self.wav_sr = self.speaker_sample_rate
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
        if not os.path.exists(recorded_speech_path):
            os.makedirs(recorded_speech_path)
        json.dump(self.recorded_audio, open(recorded_speech_filename, "w+"))

    def save_audio_file(self, file, data):
        sf.write(file, data, self.speaker_sample_rate, subtype='PCM_16')
        
        if self.child and IS_FFMPEG:
            ffmpeg_path = shutil.which("ffmpeg")
            
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
        
        # First, try to find HDMI audio output
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and "dp" in d["name"].lower():
                print(f"Using HDMI speaker: {d['name']}")
                return i, int(d['default_samplerate'])
        
        # Fallback: try USB
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and "hdmi" in d["name"]:
                print(f"Using USB speaker: {d['name']}")
                return i, int(d['default_samplerate'])
        
        # Fallback: first available output
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0:
                print(f"Using default speaker: {d['name']}")
                return i, int(d['default_samplerate'])

    # def get_usb_speaker(self):
    #     devices = sd.query_devices()
    #     for i, d in enumerate(devices):
    #         if d['max_output_channels'] > 0 and "USB" in d["name"]:
    #             print("Using USB speaker:", d["name"])
    #             return i
    #     # No USB speaker, find another one
    #     for i, d in enumerate(devices):
    #         if d['max_output_channels'] > 0:
    #             return i
    
    def generate_speech_text(self, text=None, file=None):
        print("Generating speech ... ", text)
        # Synthesize speech
        
        # Added new TTS on the robot
        # if IS_ROBOT:
        #     return None

        if len(self.languages) == 1:
            if TTS_MODEL == "nix":
                c, c_length, _ = self.model.tokenizer([text])
                wav = self.model.vocalize(c, c_length)[0, 0].astype(np.float32)
                # wav_resampled = librosa.resample(wav, orig_sr=TTS_SAMPLE_RATE, target_sr=self.speaker_sample_rate)
                # wav = wav_resampled.astype(np.float32)
            elif TTS_MODEL == "silero" and not IS_ROBOT:
                audio = self.model.apply_tts(text=text, 
                                            speaker=self.speaker, 
                                            sample_rate=self.wav_sr)
                wav = audio.numpy()
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
                    try:
                        audio_part = self.models[part_lang].apply_tts(
                            ssml_text=ssml, speaker=self.speakers[part_lang], 
                            sample_rate=self.wav_sr)
                    except: # This deals with the issue of computer vs robot TTS and USB speakers
                        audio_part = self.models[part_lang].apply_tts(
                            ssml_text=ssml, speaker=self.speakers[part_lang], 
                            sample_rate=TTS_SAMPLE_RATE)

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
            if self.wav_sr != self.speaker_sample_rate:
                stereo_audio = librosa.resample(stereo_audio, orig_sr=self.wav_sr, target_sr=self.speaker_sample_rate)
            self.save_audio_file(audio_file, stereo_audio)
            envelope = self.get_envelope(audio_file, y=wav, sr=self.speaker_sample_rate)
            # envelope = self.get_envelope(audio_file, y=stereo_audio, sr=self.speaker_sample_rate)
            if self.keep_record:
                np.save(env_file, envelope)

            self.audio_objects[audio_file] = {
                "data": stereo_audio, 
                "samplerate": self.speaker_sample_rate,
                "envelope": envelope
            }
        if SOUND_OPTION == "pygame":
            sf.write(file=audio_file, data=stereo_audio, samplerate=self.speaker_sample_rate)
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
        # if len(data.shape) > 1:
        #     data = data[:,0]


        # then if required, resample
        if samplerate != self.speaker_sample_rate:
            data = librosa.resample(data, orig_sr=samplerate, target_sr=self.speaker_sample_rate)
            # Save the resampled audio to a new file
            self.save_audio_file(file, data)
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
                candidate = pre_audio_file[0]
                if os.path.exists(candidate):
                    file = candidate
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
                        # if len(data.shape) > 1:
                        #     data = data[:,0]
                        # then if required, resample
                        if samplerate != self.speaker_sample_rate:
                            data = librosa.resample(data, orig_sr=samplerate, target_sr=self.speaker_sample_rate)
                            # Save the resampled audio to a new file
                            self.save_audio_file(audio_file, data)

                        if env_file is not None:
                            if os.path.exists(env_file):
                                try:
                                    envelope = np.load(env_file)
                                except:
                                    envelope = self.get_envelope(audio_file, y=data, sr=samplerate)
                                    if self.keep_record:
                                        np.save(env_file, envelope)
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
                    if samplerate != self.speaker_sample_rate:
                        data = librosa.resample(
                            data.T,  # librosa expects shape (channels, samples)
                            orig_sr=samplerate,
                            target_sr=self.speaker_sample_rate
                        ).T
                        sf.write(file, data, self.speaker_sample_rate)
         
                       
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
        stretch_factor = 2.0
        if stretch_factor != 1.0:
            old_indices = np.arange(len(envelope))
            new_length = int(len(envelope) * stretch_factor)
            new_indices = np.linspace(0, len(envelope) - 1, new_length)
            envelope = np.interp(new_indices, old_indices, envelope)
            
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


    
    def _aplay(self, file, stop_event=None):
        """Play a WAV file via aplay (OrangePi/Linux only)."""
        proc = _subprocess.Popen(
            ["aplay", "-D", APLAY_DEVICE, file],
            stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL
        )
        while proc.poll() is None:
            if stop_event is not None and stop_event.is_set():
                proc.terminate()
                break
            sleep_time.sleep(0.05)

    def generate_audio(self, text=None, file=None, stop_event=None, stop_condition=None):
        file = self.update_audio_objects(text=text, file=file)

        if SOUND_OPTION == "pygame":
            if IS_ROBOT:
                self._aplay(file, stop_event)
            else:
                sound = self.audio_objects[file]["sound"]
                with self.pygame_lock:
                    sound.play()
                    duration_ms = int(sound.get_length() * 1000)
                    clock = time.Clock()
                    elapsed = 0
                    while elapsed < duration_ms:
                        elapsed += clock.tick(30)
                        if stop_event is not None and stop_event.is_set():
                            break
                    sound.stop()
                    if AUDIO_DELAY:
                        sleep_time.sleep(AUDIO_DELAY)
                    if stop_condition is not None:
                        if "audio" in stop_condition:
                            stop_event.set()
        elif SOUND_OPTION == "sounddevice":
            sd.play(self.audio_objects[file]["data"], samplerate=self.audio_objects[file]["samplerate"])
            sd.wait()

    def play_audio(self, file, stop_event=None):
        """Play an already-loaded audio_objects entry directly, skipping TTS generation."""
        if SOUND_OPTION == "pygame":
            if IS_ROBOT:
                self._aplay(file, stop_event)
            else:
                sound = self.audio_objects[file]["sound"]
                with self.pygame_lock:
                    sound.play()
                    duration_ms = int(sound.get_length() * 1000)
                    clock = time.Clock()
                    elapsed = 0
                    while elapsed < duration_ms:
                        elapsed += clock.tick(30)
                        if stop_event is not None and stop_event.is_set():
                            break
                    sound.stop()
                    if AUDIO_DELAY:
                        sleep_time.sleep(AUDIO_DELAY)
        elif SOUND_OPTION == "sounddevice":
            sd.play(self.audio_objects[file]["data"], samplerate=self.audio_objects[file]["samplerate"])
            sd.wait()

    def audio_thread(self, text=None, file=None):
        stop_event = threading.Event()
        t = threading.Thread(target=self.generate_audio, args=(text, file, stop_event, None))
        return t

    def play_audio_thread(self, file):
        """Thread that plays a pre-loaded audio object with no TTS overhead."""
        stop_event = threading.Event()
        t = threading.Thread(target=self.play_audio, args=(file, stop_event))
        return t
    
    def run_speech(self, text=None, file=None):
        audio_thread = self.audio_thread(text, file)
        audio_thread.start()
        audio_thread.join()

if __name__ == "__main__":
    # speech = Speech(languages=["en", "es"], child=True, verbose=True)
    speech = Speech(languages=["en"], child=False, verbose=True)
    speech.set_activity("test_speech")
    # speech.run_speech(text="ten we're going to build a Ferris wheel. Or in Spanish, we say. #la noria.# Do you know what a Ferris wheel is? Tell your friends.")
    # speech.run_speech(text="¡Hola, mundo dos!")
    # speech.run_speech(text="Hi everyone you goren. We are going to build a Ferris wheel. Four.")
    # speech.run_speech(file="../Assets/teacher/laugh.wav")
    # speech.run_speech(file="../Assets/audio/demo_01_greetings.wav")
    tts_text = sys.argv[1] if len(sys.argv) > 1 else None
    if tts_text is not None:
        speech.run_speech(text=tts_text)
    else:
        speech.run_speech(text="Test number one")
