
from hearingDefinitions import *
import sounddevice as sd
import threading

language_models = None
HEARING_OPTION = "vosk"
if HEARING_OPTION == "sr":
    import speech_recognition as sr
elif HEARING_OPTION == "whisper":
    import whisper
    import numpy as np
    import queue
    import time
    from hearingDefinitions import *
elif HEARING_OPTION == "vosk":
    import json
    from vosk import Model, KaldiRecognizer
    import pyaudio

    language_models = {
        "en": "../Resources/vosk-model-small-en-us-0.15",
        "es": "../Resources/vosk-model-small-es-0.42"
    }
    



class Hearing():
    def __init__(self, languages="en", verbose=False):
        print("Initializing hearing ...")
        self.verbose = verbose
        self.recognizer = None
        self.texts = []
        self.mic_index = self.get_usb_microphone()
        if HEARING_OPTION == "sr":
            self.recognizer = sr.Recognizer()
        elif HEARING_OPTION == "whisper":
            # Whisper model
            self.model = whisper.load_model("tiny")
            # Queue to hold audio chunks
            self.audio_queue = queue.Queue()
        elif HEARING_OPTION == "vosk":
            self.languages = []
            if isinstance(languages, str):
                self.languages.append(languages)
            elif isinstance(languages, list):
                self.languages = languages
            
            self.model = {}
            if language_models:
                for lang in self.languages:
                    if lang in language_models:
                        self.model[lang] = Model(language_models[lang])
            self.words = '["yes", "no", "[unk]"]'
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(input_device_index=self.mic_index,format=pyaudio.paInt16, 
                                 channels=1, rate=INPUT_SAMPLE_RATE, 
                                 input=True, frames_per_buffer=int(INPUT_SAMPLE_RATE/4))

        
    def get_usb_microphone(self):
        devices = sd.query_devices()
        usb_devices = [
            i for i, device in enumerate(devices) if device['max_input_channels'] > 0 and "USB" in device["name"]
        ]
        if len(usb_devices) > 0:
            usb_device = usb_devices[0]
            return usb_device
        else:
            return None

    def merge_confidence_generic(self, all_words, min_interval=0.01):
        """
        Given a flat list of word dicts (each with 'start','end','conf','word'),
        split the timeline at every unique boundary and for each interval pick
        the word with the highest confidence—ignoring intervals shorter than min_interval.
        """
        # 1) collect and sort all unique time boundaries
        boundaries = sorted({t for w in all_words for t in (w['start'], w['end'])})
        merged, last_word = [], None

        # 2) for each adjacent interval, pick the covering word with highest conf
        for t0, t1 in zip(boundaries, boundaries[1:]):
            if (t1 - t0) < min_interval:
                # skip very tiny slices (e.g. <20ms)
                continue

            # proper coverage: word must start at or before t0 AND end at or after t1
            covering = [w for w in all_words if w['start'] <= t0 and w['end'] >= t1]
            if not covering:
                continue
            best = max(covering, key=lambda w: w['conf'])
            if best['word'] != last_word:
                merged.append({'word': best['word'], 'lang': best['lang']})
                last_word = best['word']

        return merged

    def detect_words(self, unique_words=None, words_heard=None):
        words_detected = []
        # if there are self.words, only append if there's a match
        for w in words_heard:
            for phrase, phrase_words in unique_words.items():
                if w['word'] in phrase_words:
                    words_detected.append(phrase)
                    break
        if len(words_detected) > 0:
            return words_detected
        else:
            return None

    def listen(self, stop_event=None):
        unique_words = []
        if self.words:
            all_phrase_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
            unique_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
            # print("all_phrase_words: ", all_phrase_words)
            for phrase, phrase_words in all_phrase_words.items():                    
                for phrase2, phrase2_words in all_phrase_words.items():
                    if phrase != phrase2:
                        unique_words[phrase] -= phrase2_words
            # print("unique_words: ", unique_words)                            



        if HEARING_OPTION == "sr":
            with sr.Microphone(device_index=self.mic_index) as source:
                print("Adjusting for ambient noise... Please wait.")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("Listening for speech...")

                try:
                    audio = self.recognizer.listen(source, timeout=10)
                    print("Processing speech...")
                    text = self.recognizer.recognize_sphinx(audio)
                    self.texts.append(text)
                    print(f"Recognized speech: {text}")
                    if stop_event is not None:
                        stop_event.set()
                except sr.WaitTimeoutError:
                    print("No speech detected within the timeout period.")
                except sr.UnknownValueError:
                    print("Speech was unclear or not recognized.")
                except sr.RequestError as e:
                    print(f"Error with the speech recognition engine: {e}")
        elif HEARING_OPTION == "whisper":
            self.audio_queue = queue.Queue()
            # Silence detection variables
            last_non_silent_time = time.time()
            # Open the audio stream
            text = ""
            if self.verbose:
                devices = sd.query_devices()
                print("Selected device: ", self.mic_index, devices[self.mic_index])

            with sd.InputStream(samplerate=INPUT_SAMPLE_RATE, channels=1, 
                                device=self.mic_index, callback=self.audio_callback, blocksize=12000):
                print("Listening... Speak into the microphone.")
                audio_buffer = np.zeros((0,), dtype=np.float32)

                while True:
                    if self.verbose:
                        print("processing ...")
                    # Get the audio chunk from the queue
                    chunk = self.audio_queue.get()
                    audio_buffer = np.append(audio_buffer, chunk.flatten())

                    # Process in CHUNK_DURATION segments
                    if len(audio_buffer) >= INPUT_SAMPLE_RATE * CHUNK_DURATION:
                        audio_chunk = audio_buffer[:INPUT_SAMPLE_RATE * CHUNK_DURATION]
                        audio_buffer = audio_buffer[INPUT_SAMPLE_RATE * CHUNK_DURATION:]

                        # Check for silence
                        if self.is_silent(audio_chunk):
                            if time.time() - last_non_silent_time > SILENCE_DURATION:
                                if len(text) > 10:
                                    print("Silence detected. Stopping transcription.")
                                    break
                        else:
                            last_non_silent_time = time.time()

                        # Transcribe the audio chunk
                        # audio_chunk = (audio_chunk * 32767).astype(np.int16)  # Convert to 16-bit PCM
                        result = self.model.transcribe(audio_chunk, fp16=False)
                        print(f"Transcription: {result['text']}")
                        text += result['text']
                self.texts.append(text)
                if stop_event is not None:
                        stop_event.set()
        elif HEARING_OPTION == "vosk":
            recognizers = {}
            for lang, model in self.model.items():
                if self.words:
                    rec = KaldiRecognizer(model, INPUT_SAMPLE_RATE, self.words)
                else:
                    rec = KaldiRecognizer(model, INPUT_SAMPLE_RATE)
                rec.SetWords(True)
                recognizers[lang] = rec
            print("Start listtening ...")
            
            self.stream.start_stream()
            self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)

            # read + feed until any recognizer signals "final"
            while True:
                data = self.stream.read(int(INPUT_SAMPLE_RATE / 4),
                                        exception_on_overflow=False)
                # feed all recognizers, check for any final result
                words_heard = []
                for lang, r in recognizers.items():
                    r.AcceptWaveform(data)
                    partial_result = r.PartialResult()
                    try:
                        partial_json = json.loads(partial_result)['partial']
                        if len(partial_json) > 0:
                            all_partial_words = partial_json.split(' ')
                            for apw in all_partial_words:
                                words_heard.append({"lang": lang, "word": apw})
                    except Exception as e:
                        print(f"Error parsing partial result for {lang}: {e}")
                words_detected = self.detect_words(unique_words=unique_words, words_heard=words_heard)
                # if any(r.AcceptWaveform(data) for r in recognizers.values()):
                #     break
                if words_detected:
                    break
            # stop mic
            self.stream.stop_stream()

            # gather every word hypothesis from every model
            all_words = []
            for lang, rec in recognizers.items():
                res = json.loads(rec.FinalResult())
                for w in res.get("result", []):
                    w["lang"] = lang
                    all_words.append(w)
            for lang, rec in recognizers.items():
                rec.Reset()

            if len(all_words) == 0:     # got enough information from partial results, don't need final results
                for wd in words_detected:
                    self.texts.append(phrase)
            # merge and store
            merged = self.merge_confidence_generic(all_words)
            words = " ".join(f"{w['word']}" for w in merged)
            # if there are self.words, only append if there's a match
            if self.words:
                all_phrase_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
                unique_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
                for phrase, phrase_words in all_phrase_words.items():                    
                    for phrase2, phrase2_words in all_phrase_words.items():
                        if phrase != phrase2:
                            unique_words[phrase] -= phrase2_words
                for w in merged:
                    for phrase, phrase_words in unique_words.items():
                        # print("phrase: ", phrase, "phrase_words: ", phrase_words, "== w['word']: ", w['word'])
                        if w['word'] in phrase_words:
                            if phrase not in self.texts:
                                self.texts.append(phrase)
                            break
            else:
                # no self.words, just append all
                self.texts.append(words)

            if stop_event is not None:
                stop_event.set()

    # Function to capture audio in real-time    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback function to capture audio chunks."""
        if status:
            print(f"Status: {status}")
        self.audio_queue.put(indata.copy())

    # Function to check if audio is silent
    def is_silent(self, audio):
        """Detect if audio chunk is silent."""
        return np.abs(audio).mean() < SILENCE_THRESHOLD

    # Function to check audio levels
    def check_audio_levels(self, audio_chunk):
        """Display the average audio amplitude to verify microphone input."""
        avg_amplitude = np.abs(audio_chunk).mean()
        # print(f"Average amplitude: {avg_amplitude:.6f}")
        return avg_amplitude


    def hearing_thread(self, stop_event=None):
        if stop_event is None:
            stop_event = threading.Event()
        t = threading.Thread(target=self.listen, args=[stop_event])
        return t
    
    def run_hearing(self):
        hearing_thread = self.hearing_thread()
        hearing_thread.start()
        hearing_thread.join()


if __name__ == "__main__":
    hearing = Hearing(verbose=True) #, languages=["en", "es"])
    hearing.words = '["show group one", "show group two", "show group three", "done gigi"]'
    hearing.run_hearing()
    print(hearing.texts)
    print('Done!')