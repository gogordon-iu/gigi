# librosa removed for OrangePi 5 Pro optimization

IS_FFMPEG = False
try:
    import ffmpeg
    IS_FFMPEG = True
except:
    IS_FFMPEG = False

import numpy as np

def resample_linear(y, orig_sr, target_sr):
    if orig_sr == target_sr:
        return y
    if y.ndim == 1:
        duration = len(y) / orig_sr
        num_samples = int(duration * target_sr)
        old_x = np.linspace(0, duration, len(y))
        new_x = np.linspace(0, duration, num_samples)
        return np.interp(new_x, old_x, y)
    else:
        if y.shape[0] < y.shape[1]:
            channels = y.shape[0]
            length = y.shape[1]
            duration = length / orig_sr
            num_samples = int(duration * target_sr)
            old_x = np.linspace(0, duration, length)
            new_x = np.linspace(0, duration, num_samples)
            resampled = np.zeros((channels, num_samples), dtype=y.dtype)
            for i in range(channels):
                resampled[i] = np.interp(new_x, old_x, y[i])
            return resampled
        else:
            length = y.shape[0]
            channels = y.shape[1]
            duration = length / orig_sr
            num_samples = int(duration * target_sr)
            old_x = np.linspace(0, duration, length)
            new_x = np.linspace(0, duration, num_samples)
            resampled = np.zeros((num_samples, channels), dtype=y.dtype)
            for i in range(channels):
                resampled[:, i] = np.interp(new_x, old_x, y[:, i])
            return resampled

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

# ── Audio backend ────────────────────────────────────────────────────────────
SOUND_OPTION = "pygame"   # "pygame" | "sounddevice"

import soundfile as sf

if SOUND_OPTION == "pygame":
    # Must be set BEFORE pygame is imported so SDL picks up the device
    if platform.system() != "Windows":
        if "SDL_AUDIODRIVER" not in os.environ:
            os.environ["SDL_AUDIODRIVER"] = "alsa"
        if "AUDIODEV" not in os.environ:
            os.environ["AUDIODEV"] = "hw:1,0"   # OrangePi HDMI/DP SPDIF

    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
    import pygame
    from pygame import mixer
    from pygame import time as pygame_time   # avoids shadowing sleep_time

elif SOUND_OPTION == "sounddevice":
    import sounddevice as sd

# ── TTS model ─────────────────────────────────────────────────────────────────
TTS_MODEL = "nix"   # "nix" | "silero"

# eSpeak path configuration based on platform
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    ESPEAK_PATH     = r"C:/Program Files/eSpeak NG/espeak-ng.exe"
    ESPEAK_LIBRARY  = r"C:/Program Files/eSpeak NG/libespeak-ng.dll"
    TTS_MODEL = "silero"
else:
    ESPEAK_PATH     = "/usr/bin/espeak-ng"
    ESPEAK_LIBRARY  = None

if TTS_MODEL == "nix":
    _speech_dir = os.path.dirname(os.path.abspath(__file__))
    _gigi_dir = os.path.dirname(_speech_dir)
    _resources_dir = os.path.join(_gigi_dir, 'Resources')
    if _resources_dir not in sys.path:
        sys.path.insert(0, _resources_dir)

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
    'en':    ('v3_en',    {'female': 'en_0', 'male': 'en_1'}, TTS_SAMPLE_RATE),
    'es':    ('v3_es',    'es_1',                              TTS_SAMPLE_RATE),
    'multi': ('multi_v2', 'lj',                                8000),
}

MULTI = False


# ─────────────────────────────────────────────────────────────────────────────
class Speech():

    def __init__(self, languages="en", activity=None, child=False, gender='female', verbose=False):
        self.activity   = activity
        self.verbose    = verbose
        self.child      = child
        self.gender     = gender
        print("Initializing speech ...")
        self.sample_rate   = 0.1
        self.audio_objects = {}
        self.recorded_audio = {}
        self.keep_record    = True
        self.set_activity(activity_name=activity)

        if os.path.exists(recorded_speech_filename):
            self.recorded_audio = json.load(open(recorded_speech_filename, "r"))
        else:
            self.save_recorded_audio()

        self.speaker_sample_rate = TTS_SAMPLE_RATE

        if SOUND_OPTION == "pygame":
            self._init_pygame_mixer()
            self.device_samplerate = self.speaker_sample_rate

        elif SOUND_OPTION == "sounddevice":
            speaker_device, self.device_samplerate = self.get_usb_speaker()
            sd.default.device = (None, speaker_device)

        # ── Load TTS model ────────────────────────────────────────────────
        self.languages = []
        if isinstance(languages, str):
            self.languages.append(languages)
        elif isinstance(languages, list):
            self.languages = languages

        if len(self.languages) == 1:
            if TTS_MODEL == "silero" and not IS_ROBOT:
                self.model, example_text = torch.hub.load(
                    repo_or_dir='snakers4/silero-models',
                    model='silero_tts',
                    language=self.languages[0],
                    speaker=lanugage_speakers[self.languages[0]][0])
            elif TTS_MODEL == "nix":
                _speech_dir = os.path.dirname(os.path.abspath(__file__))
                _gigi_dir = os.path.dirname(_speech_dir)
                _model_dir = os.path.join(_gigi_dir, 'Resources', 'nix', 'models')
                self.model = NixTTSInference(model_dir=_model_dir)
            else:
                self.model = None

            lang_entry = lanugage_speakers[self.languages[0]][1]
            if isinstance(lang_entry, dict):
                self.speaker = lang_entry.get(self.gender, next(iter(lang_entry.values())))
            else:
                self.speaker = lang_entry
            self.wav_sr = lanugage_speakers[self.languages[0]][2]

        else:
            if MULTI:
                self.model, _ = torch.hub.load(
                    'snakers4/silero-models', 'silero_tts',
                    language='multi',
                    speaker=lanugage_speakers['multi'][0])
                self.speaker = lanugage_speakers['multi'][1]
                self.wav_sr  = lanugage_speakers['multi'][2]
            else:
                self.models   = []
                self.speakers = []
                self.wav_sr   = self.speaker_sample_rate
                for lang in self.languages:
                    model, _ = torch.hub.load(
                        repo_or_dir='snakers4/silero-models',
                        model='silero_tts',
                        language=lang,
                        speaker=lanugage_speakers[lang][0])
                    self.models.append(model)
                    lang_entry = lanugage_speakers[lang][1]
                    if isinstance(lang_entry, dict):
                        speaker = lang_entry.get(self.gender, next(iter(lang_entry.values())))
                    else:
                        speaker = lang_entry
                    self.speakers.append(speaker)

    # ── pygame mixer init ─────────────────────────────────────────────────────
    def _init_pygame_mixer(self):
        """Initialize pygame mixer with OrangePi hw:1,0 SPDIF-compatible settings."""
        pygame.init()

        # 48 kHz is the native rate for most HDMI/DP SPDIF devices
        configs = [
            (48000, -16, 2, 4096),
            (48000, -16, 1, 4096),
            (44100, -16, 2, 4096),
            (44100, -16, 1, 4096),
            (self.speaker_sample_rate, -16, 2, 4096),
            (self.speaker_sample_rate, -16, 1, 4096),
        ]

        for freq, size, channels, buf in configs:
            try:
                mixer.quit()
                mixer.pre_init(frequency=freq, size=size, channels=channels, buffer=buf)
                mixer.init()
                actual_freq, actual_size, actual_channels = mixer.get_init()
                print(f"pygame mixer OK — freq={actual_freq} size={actual_size} "
                      f"channels={actual_channels} buf={buf}")
                self.speaker_sample_rate = actual_freq
                self.pygame_lock = threading.Lock()
                return
            except Exception as e:
                print(f"pygame mixer attempt failed ({freq} Hz, ch={channels}): {e}")

        raise RuntimeError(
            "Could not initialize pygame mixer. "
            "Check that hw:1,0 is available: run  aplay -l  and verify.")

    # ── Activity helpers ──────────────────────────────────────────────────────
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
                .filter('atempo', 1 / 1.3348)
                .output('../Assets/recorded_speech/child.wav')
                .overwrite_output()
                .run(cmd=ffmpeg_path)
            )
            os.remove(file)
            shutil.copy('../Assets/recorded_speech/child.wav', file)

    # ── Device discovery (sounddevice only) ───────────────────────────────────
    def get_usb_speaker(self):
        devices = sd.query_devices()

        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and "dp" in d["name"].lower():
                print(f"Using HDMI speaker: {d['name']}")
                return i, int(d['default_samplerate'])

        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0 and "hdmi" in d["name"].lower():
                print(f"Using USB speaker: {d['name']}")
                return i, int(d['default_samplerate'])

        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0:
                print(f"Using default speaker: {d['name']}")
                return i, int(d['default_samplerate'])

    # ── TTS synthesis ─────────────────────────────────────────────────────────
    def generate_speech_text(self, text=None, file=None):
        print("Generating speech ... ", text)

        if len(self.languages) == 1:
            if TTS_MODEL == "nix":
                c, c_length, _ = self.model.tokenizer([text])
                wav = self.model.vocalize(c, c_length)[0, 0].astype(np.float32)
            elif TTS_MODEL == "silero" and not IS_ROBOT:
                audio = self.model.apply_tts(
                    text=text, speaker=self.speaker, sample_rate=self.wav_sr)
                wav = audio.numpy()
        else:
            if MULTI:
                audio = self.model.apply_tts(
                    texts=[text], speakers=[self.speaker], sample_rate=self.wav_sr)[0]
                wav = audio.numpy()
            else:
                text_parts = text.split("#")
                num_parts  = 0
                for i, part in enumerate(text_parts):
                    if len(part) == 0:
                        continue
                    part_lang = i % 2
                    rate = "slow" if part_lang == 1 else "fast"
                    ssml = (f'<speak><prosody pitch="low">'
                            f'<prosody rate="{rate}"> {part}</prosody>'
                            f'</prosody></speak>')
                    try:
                        audio_part = self.models[part_lang].apply_tts(
                            ssml_text=ssml, speaker=self.speakers[part_lang],
                            sample_rate=self.wav_sr)
                    except:
                        audio_part = self.models[part_lang].apply_tts(
                            ssml_text=ssml, speaker=self.speakers[part_lang],
                            sample_rate=TTS_SAMPLE_RATE)

                    audio = audio_part if num_parts == 0 else torch.cat((audio, audio_part), dim=0)
                    num_parts += 1
                wav = audio.numpy()

        stereo_audio = np.column_stack((wav, wav))

        if self.keep_record:
            audio_file = self.activity_speech_path + generate_random_filename(extension="wav")
            self.recorded_audio[self.activity] = {
                k: v for k, v in self.recorded_audio[self.activity].items() if v != text}
            self.recorded_audio[self.activity][audio_file] = text
            self.save_recorded_audio()
        else:
            audio_file = "../temp/output.wav"

        env_file = audio_file.replace(".wav", ".npy")

        if SOUND_OPTION == "sounddevice":
            play_data = stereo_audio[:, 0] if stereo_audio.ndim > 1 else stereo_audio
            if self.wav_sr != self.speaker_sample_rate:
                play_data = resample_linear(
                    play_data, orig_sr=self.wav_sr, target_sr=self.speaker_sample_rate)
            self.save_audio_file(audio_file, play_data)
            envelope = self.get_envelope(audio_file, y=wav, sr=self.speaker_sample_rate)
            if self.keep_record:
                np.save(env_file, envelope)
            self.audio_objects[audio_file] = {
                "data":       play_data,
                "samplerate": self.speaker_sample_rate,
                "envelope":   envelope,
            }

        elif SOUND_OPTION == "pygame":
            # Resample to the actual mixer rate before writing / loading
            play_data = stereo_audio
            if self.wav_sr != self.speaker_sample_rate:
                mono = stereo_audio[:, 0] if stereo_audio.ndim > 1 else stereo_audio
                resampled = resample_linear(
                    mono, orig_sr=self.wav_sr, target_sr=self.speaker_sample_rate)
                play_data = np.column_stack((resampled, resampled))

            sf.write(file=audio_file, data=play_data, samplerate=self.speaker_sample_rate,
                     subtype='PCM_16')
            envelope = self.get_envelope(audio_file)
            if self.keep_record:
                np.save(env_file, envelope)
            self.audio_objects[audio_file] = {
                "sound":    mixer.Sound(audio_file),
                "envelope": envelope,
            }

        return audio_file

    def generate_speech_file(self, file=None):
        if not os.path.exists(file):
            file = self.activity_speech_path + file.split('/')[-1]
        if not os.path.exists(file):
            file = audio_path + file.split('/')[-1]
        if not os.path.exists(file):
            print(f"ERROR: audio file {file.split('/')[-1]} not found!")
            return None, None, None, None

        data, samplerate = sf.read(file)
        if self.verbose:
            print("DEBUG: samplerate", samplerate)

        if samplerate != self.speaker_sample_rate:
            data = resample_linear(data, orig_sr=samplerate, target_sr=self.speaker_sample_rate)
            self.save_audio_file(file, data)

        envelope = self.get_envelope(file, y=data, sr=samplerate)

        if self.keep_record:
            audio_file = self.activity_speech_path + file.split('/')[-1]
            shutil.copy(file, audio_file)
            env_file = audio_file.replace(".wav", ".npy")
            np.save(env_file, envelope)
            self.recorded_audio[self.activity] = {
                k: v for k, v in self.recorded_audio[self.activity].items()
                if v != file.split('/')[-1]}
            self.recorded_audio[self.activity][audio_file] = file.split('/')[-1]
            self.save_recorded_audio()
        else:
            audio_file = file

        return audio_file, data, samplerate, envelope

    # ── Audio-object cache management ─────────────────────────────────────────
    def update_audio_objects(self, file=None, text=None):
        env_file = None
        found    = False

        if text is not None:
            pre_audio_file = [k for k, v in self.recorded_audio[self.activity].items() if v == text]
            if pre_audio_file:
                candidate = pre_audio_file[0]
                if os.path.exists(candidate):
                    file     = candidate
                    env_file = file.replace(".wav", ".npy")
                    print("Found record: ", file)
                    found = True
        elif file is not None:
            pre_audio_file = [k for k, v in self.recorded_audio[self.activity].items() if v == file]
            for f in pre_audio_file:
                if os.path.exists(f):
                    file     = f
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
                    envelope = (np.load(env_file)
                                if env_file and os.path.exists(env_file)
                                else self.get_envelope(audio_file))
                    self.audio_objects[audio_file] = {
                        "sound":    mixer.Sound(audio_file),
                        "envelope": envelope,
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
                            return self.update_audio_objects(text=text, file=None)

                    if loaded_audio:
                        if samplerate != self.speaker_sample_rate:
                            data = resample_linear(
                                data, orig_sr=samplerate, target_sr=self.speaker_sample_rate)
                            self.save_audio_file(audio_file, data)

                        if env_file and os.path.exists(env_file):
                            try:
                                envelope = np.load(env_file)
                            except:
                                envelope = self.get_envelope(audio_file, y=data, sr=samplerate)
                                if self.keep_record:
                                    np.save(env_file, envelope)
                        else:
                            envelope = self.get_envelope(audio_file, y=data, sr=samplerate)
                            if self.keep_record and env_file:
                                np.save(env_file, envelope)

                        self.audio_objects[audio_file] = {
                            "data":       data,
                            "samplerate": samplerate,
                            "envelope":   envelope,
                        }
                    else:
                        audio_file = self.generate_speech_text(text=text)

        elif file is not None:
            if not found:
                if SOUND_OPTION == "sounddevice":
                    audio_file, data, samplerate, envelope = self.generate_speech_file(file=file)
                elif SOUND_OPTION == "pygame":
                    audio_file, data, samplerate, envelope = self.generate_speech_file(file=file)
                    if audio_file:
                        self.audio_objects[audio_file] = {
                            "sound":    mixer.Sound(audio_file),
                            "envelope": envelope,
                        }
            else:
                audio_file = file
                data, samplerate = sf.read(file)

                if samplerate != self.speaker_sample_rate:
                    data = resample_linear(
                        data.T if data.ndim > 1 else data,
                        orig_sr=samplerate, target_sr=self.speaker_sample_rate).T
                    sf.write(file, data, self.speaker_sample_rate)

                envelope = (np.load(env_file)
                            if env_file and os.path.exists(env_file)
                            else self.get_envelope(file, y=data, sr=samplerate))
                if self.keep_record and env_file and not os.path.exists(env_file):
                    np.save(env_file, envelope)

                if SOUND_OPTION == "pygame":
                    self.audio_objects[audio_file] = {
                        "sound":    mixer.Sound(audio_file),
                        "envelope": envelope,
                    }
                elif SOUND_OPTION == "sounddevice":
                    self.audio_objects[audio_file] = {
                        "data":       data,
                        "samplerate": samplerate,
                        "envelope":   envelope,
                    }

        return audio_file

    # ── Envelope extraction ───────────────────────────────────────────────────
    def get_envelope(self, file, max_length=-1, y=None, sr=None):
        if y is None and sr is None:
            y, sr = sf.read(file)
        if max_length > 0:
            y = y[:sr * max_length]
            
        # Ensure y is mono
        if y.ndim > 1:
            y = y.mean(axis=1) if y.shape[0] > y.shape[1] else y.mean(axis=0)

        # Calculate RMS envelope
        hop_length = int(sr * self.sample_rate)
        if hop_length <= 0:
            return np.array([0.0])

        num_frames = int(np.ceil(len(y) / hop_length))
        envelope = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_length
            end = min(start + hop_length, len(y))
            frame = y[start:end]
            if len(frame) > 0:
                envelope[i] = np.sqrt(np.mean(frame**2))

        stretch_factor = 1.5
        if stretch_factor != 1.0 and len(envelope) > 1:
            old_indices = np.arange(len(envelope))
            new_length  = int(len(envelope) * stretch_factor)
            new_indices = np.linspace(0, len(envelope) - 1, new_length)
            envelope    = np.interp(new_indices, old_indices, envelope)

        max_val = np.max(envelope)
        if max_val > 0:
            envelope = envelope / max_val
        envelope = np.minimum(envelope * 4, 1.0)
        return envelope

    # ── Playback ──────────────────────────────────────────────────────────────
    def generate_audio(self, text=None, file=None, stop_event=None, stop_condition=None):
        file = self.update_audio_objects(text=text, file=file)

        if SOUND_OPTION == "pygame":
            sound = self.audio_objects[file]["sound"]
            with self.pygame_lock:
                sound.play()
                duration_ms = int(sound.get_length() * 1000)
                clock   = pygame_time.Clock()   # ← pygame_time, not time
                elapsed = 0
                while elapsed < duration_ms:
                    elapsed += clock.tick(30)
                    if stop_event is not None and stop_event.is_set():
                        break
                sound.stop()
                if AUDIO_DELAY:
                    sleep_time.sleep(AUDIO_DELAY)
                if stop_condition is not None and "audio" in stop_condition:
                    stop_event.set()

        elif SOUND_OPTION == "sounddevice":
            self._sd_play(file, stop_event)

    def play_audio(self, file, stop_event=None):
        """Play an already-loaded audio_objects entry directly."""
        if SOUND_OPTION == "pygame":
            sound = self.audio_objects[file]["sound"]
            with self.pygame_lock:
                sound.play()
                duration_ms = int(sound.get_length() * 1000)
                clock   = pygame_time.Clock()   # ← pygame_time
                elapsed = 0
                while elapsed < duration_ms:
                    elapsed += clock.tick(30)
                    if stop_event is not None and stop_event.is_set():
                        break
                sound.stop()
                if AUDIO_DELAY:
                    sleep_time.sleep(AUDIO_DELAY)

        elif SOUND_OPTION == "sounddevice":
            self._sd_play(file, stop_event)

    def _sd_play(self, file, stop_event=None):
        """Play via sounddevice, resampling to device native rate if needed."""
        data     = self.audio_objects[file]["data"]
        src_rate = self.audio_objects[file]["samplerate"]
        if src_rate != self.device_samplerate:
            data = resample_linear(
                data.T if data.ndim > 1 else data,
                orig_sr=src_rate, target_sr=self.device_samplerate)
            if data.ndim > 1:
                # If resample_linear returned (channels, length), transpose back to (length, channels)
                if data.shape[0] < data.shape[1]:
                    data = data.T
        sd.play(data, samplerate=self.device_samplerate)
        while sd.get_stream().active:
            if stop_event is not None and stop_event.is_set():
                sd.stop()
                break
            sleep_time.sleep(0.05)

    # ── Thread helpers ────────────────────────────────────────────────────────
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


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    speech = Speech(languages=["en"], child=False, verbose=True)
    speech.set_activity("test_speech")
    tts_text = sys.argv[1] if len(sys.argv) > 1 else None
    if tts_text is not None:
        speech.run_speech(text=tts_text)
    else:
        speech.run_speech(text="Test number one")