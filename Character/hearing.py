from hearingDefinitions import *
import sounddevice as sd
import threading
import json
import webrtcvad
import numpy as np

language_models = None
HEARING_OPTION = "whisper"
if HEARING_OPTION == "sr":
    import speech_recognition as sr
elif HEARING_OPTION == "whisper":
    from faster_whisper import WhisperModel
    import numpy as np
    import queue
    import time
    from hearingDefinitions import (
        INPUT_SAMPLE_RATE, TARGET_SAMPLE_RATE, SILENCE_DURATION,
        NO_SPEECH_THRESHOLD, VAD_FILTER, REPETITION_PENALTY,
        BEAM_SIZE, BEST_OF
    )
    from whisper_helper import WhisperAudioProcessor, transcribe_optimized, calibrate_energy_threshold
elif HEARING_OPTION == "vosk":
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
        self.words = None
        self.texts = []
        self.mic_index = self.get_usb_microphone()

        # Buffer to store raw audio for speaker recognition
        self.raw_audio_buffer = []

        if HEARING_OPTION == "sr":
            self.recognizer = sr.Recognizer()
        elif HEARING_OPTION == "whisper":
            self.model = WhisperModel("base", device="cpu", compute_type="int8")

            self.audio_processor = WhisperAudioProcessor(
                native_sample_rate=INPUT_SAMPLE_RATE,
                target_sample_rate=TARGET_SAMPLE_RATE,
                energy_threshold=500,
                buffer_duration=2.0,
                min_audio_length=0.75,
                silence_duration=SILENCE_DURATION,
                debug=verbose
            )

            # WebRTC VAD configuration
            self.vad = webrtcvad.Vad(2)  # Aggressiveness level 2 — more robust to noise than 1
            self.vad_frame_duration = 30  # ms (10, 20, or 30)
            self.vad_frame_size = int(TARGET_SAMPLE_RATE * self.vad_frame_duration / 1000)
            self.speech_threshold = 0.10

            # Single VAD-driven silence timer — updated only when WebRTC confirms speech
            self.last_vad_speech_time = None

            # Word-level deduplication
            self.last_segment_words = []

            # Queue to hold audio chunks
            self.audio_queue = queue.Queue(maxsize=5)

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
            self.stream = self.p.open(
                input_device_index=self.mic_index,
                format=pyaudio.paInt16,
                channels=1,
                rate=INPUT_SAMPLE_RATE,
                input=True,
                frames_per_buffer=int(INPUT_SAMPLE_RATE / 4)
            )

    def get_usb_microphone(self):
        devices = sd.query_devices()
        usb_devices = [
            i for i, device in enumerate(devices)
            if device['max_input_channels'] > 0 and "USB" in device["name"]
        ]
        if len(usb_devices) > 0:
            return usb_devices[0]
        return None

    def contains_speech(self, audio_data):
        """
        Check if audio chunk contains speech using WebRTC VAD.
        Returns True if speech ratio meets threshold.
        """
        audio_bytes = audio_data.astype(np.int16).tobytes()
        speech_frames = 0
        total_frames = 0

        for i in range(0, len(audio_bytes), self.vad_frame_size * 2):
            frame = audio_bytes[i:i + self.vad_frame_size * 2]
            if len(frame) < self.vad_frame_size * 2:
                continue
            try:
                if self.vad.is_speech(frame, TARGET_SAMPLE_RATE):
                    speech_frames += 1
                total_frames += 1
            except:
                continue

        if total_frames == 0:
            return False
        return (speech_frames / total_frames) >= self.speech_threshold

    def remove_duplicate_words(self, current_words):
        """
        Remove duplicate words from overlapping transcription chunks
        using word-level deduplication.
        """
        if not current_words:
            return []

        if self.last_segment_words:
            overlap_length = 0
            for i in range(1, min(len(self.last_segment_words), len(current_words)) + 1):
                if self.last_segment_words[-i:] == current_words[:i]:
                    overlap_length = i
            unique_words = current_words[overlap_length:]
        else:
            unique_words = current_words

        self.last_segment_words = current_words[-10:] if len(current_words) > 10 else current_words
        return unique_words

    def _is_hallucination(self, text: str) -> bool:
        """
        Detect Whisper hallucinations: repeated 4-word phrases appearing
        more than twice are a strong signal of looping on silence/noise.
        """
        words = text.strip().split()
        if len(words) < 6:
            return False
        for i in range(len(words) - 3):
            chunk = " ".join(words[i:i + 4])
            if text.count(chunk) > 2:
                return True
        return False

    def transcribe_with_dedup(self, audio_float, language="en"):
        """
        Transcribe audio with Whisper using parameters from hearingDefinitions,
        plus word-level deduplication and hallucination guard.
        """
        if len(audio_float) < 8000:  # Skip clips shorter than ~0.5s at 16kHz
            return ""

        try:
            segments, info = self.model.transcribe(
                audio_float,
                beam_size=BEAM_SIZE,
                best_of=BEST_OF,
                language=language,
                condition_on_previous_text=False,
                word_timestamps=True,
                vad_filter=VAD_FILTER,
                no_speech_threshold=NO_SPEECH_THRESHOLD,
                repetition_penalty=REPETITION_PENALTY,
                compression_ratio_threshold=2.4,
                temperature=0.0
            )

            current_words = []
            for segment in segments:
                words = segment.text.strip().split()
                current_words.extend(words)

            if not current_words:
                return ""

            unique_words = self.remove_duplicate_words(current_words)
            if not unique_words:
                return ""

            result = " ".join(unique_words)

            if self._is_hallucination(result):
                if self.verbose:
                    print("[VAD] Hallucination detected, discarding.")
                return ""

            return result

        except Exception as e:
            if self.verbose:
                print(f"Transcription error: {e}")
            return ""

    def merge_confidence_generic(self, all_words, min_interval=0.01):
        """
        Given a flat list of word dicts (each with 'start','end','conf','word'),
        split the timeline at every unique boundary and for each interval pick
        the word with the highest confidence, ignoring intervals shorter than min_interval.
        """
        boundaries = sorted({t for w in all_words for t in (w['start'], w['end'])})
        merged, last_word = [], None

        for t0, t1 in zip(boundaries, boundaries[1:]):
            if (t1 - t0) < min_interval:
                continue
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
        for w in words_heard:
            for phrase, phrase_words in unique_words.items():
                if w['word'] in phrase_words:
                    words_detected.append(phrase)
                    break
        return words_detected if words_detected else None

    def listen(self, stop_event=None):
        unique_words = []
        if self.words:
            all_phrase_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
            unique_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
            for phrase, phrase_words in all_phrase_words.items():
                for phrase2, phrase2_words in all_phrase_words.items():
                    if phrase != phrase2:
                        unique_words[phrase] -= phrase2_words

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
            self.last_vad_speech_time = None
            text = ""

            # Reset deduplication state for new listening session
            self.last_segment_words = []

            with sd.InputStream(
                samplerate=INPUT_SAMPLE_RATE,
                channels=1,
                device=self.mic_index,
                callback=self.audio_callback_optimized,
                blocksize=8192,
                dtype='int16'
            ):
                print("Listening... Speak into the microphone.")

                while True:
                    try:
                        audio_float = self.audio_queue.get(timeout=0.3)
                    except queue.Empty:
                        # No VAD-confirmed speech chunk — check if we should stop
                        if (
                            self.last_vad_speech_time is not None
                            and len(text.split()) >= 1
                            and time.time() - self.last_vad_speech_time > SILENCE_DURATION
                        ):
                            print("Silence detected. Stopping transcription.")
                            break
                        continue

                    # Got a VAD-confirmed chunk — transcribe it
                    self.raw_audio_buffer.append(audio_float)
                    transcription = self.transcribe_with_dedup(audio_float, language="en")

                    if transcription:
                        print(f"Transcription: {transcription}")
                        text += transcription + " "

                    if self.verbose:
                        vad_age = time.time() - self.last_vad_speech_time if self.last_vad_speech_time else 0
                        print(f"words: {len(text.split())}, silence: {vad_age:.1f}s")

                if text.strip():
                    self.texts.append(text.strip())

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
            print("Start listening ...")

            self.stream.start_stream()
            self.stream.read(self.stream.get_read_available(), exception_on_overflow=False)

            while True:
                data = self.stream.read(int(INPUT_SAMPLE_RATE / 4), exception_on_overflow=False)
                words_heard = []
                for lang, r in recognizers.items():
                    r.AcceptWaveform(data)
                    partial_result = r.PartialResult()
                    try:
                        partial_json = json.loads(partial_result)['partial']
                        if len(partial_json) > 0:
                            for apw in partial_json.split(' '):
                                words_heard.append({"lang": lang, "word": apw})
                    except Exception as e:
                        print(f"Error parsing partial result for {lang}: {e}")
                words_detected = self.detect_words(unique_words=unique_words, words_heard=words_heard)
                if words_detected:
                    break

            self.stream.stop_stream()

            all_words = []
            for lang, rec in recognizers.items():
                res = json.loads(rec.FinalResult())
                for w in res.get("result", []):
                    w["lang"] = lang
                    all_words.append(w)
            for lang, rec in recognizers.items():
                rec.Reset()

            if len(all_words) == 0:
                for wd in words_detected:
                    self.texts.append(wd)

            merged = self.merge_confidence_generic(all_words)
            words = " ".join(f"{w['word']}" for w in merged)

            if self.words:
                all_phrase_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
                unique_words = {phrase: set(phrase.split()) for phrase in json.loads(self.words)}
                for phrase, phrase_words in all_phrase_words.items():
                    for phrase2, phrase2_words in all_phrase_words.items():
                        if phrase != phrase2:
                            unique_words[phrase] -= phrase2_words
                for w in merged:
                    for phrase, phrase_words in unique_words.items():
                        if w['word'] in phrase_words:
                            if phrase not in self.texts:
                                self.texts.append(phrase)
                            break
            else:
                self.texts.append(words)

            if stop_event is not None:
                stop_event.set()

    def audio_callback_optimized(self, indata, frames, time_info, status):
        """
        Audio callback with WebRTC VAD and buffering.
        Only queues audio chunks that pass the VAD speech check.
        """
        audio_data = indata.flatten().copy()
        if len(audio_data) == 0:
            return

        self.audio_processor.add_to_buffer(audio_data)

        if self.audio_processor.should_process_buffer():
            audio_float = self.audio_processor.get_buffered_audio()

            if audio_float is not None and len(audio_float) > 0:
                audio_int16 = (audio_float * 32768.0).astype(np.int16)

                if self.contains_speech(audio_int16):
                    self.last_vad_speech_time = time.time()  # VAD-driven timer
                    try:
                        self.audio_queue.put_nowait(audio_float)
                    except queue.Full:
                        try:
                            self.audio_queue.get_nowait()
                            self.audio_queue.put_nowait(audio_float)
                        except:
                            pass

    def is_silent(self, audio):
        """Detect if audio chunk is silent."""
        return np.abs(audio).mean() < SILENCE_THRESHOLD

    def check_audio_levels(self, audio_chunk):
        """Display the average audio amplitude to verify microphone input."""
        return np.abs(audio_chunk).mean()

    def get_full_audio(self):
        """
        Return all captured audio as a single numpy array at 16kHz.
        Useful for speaker recognition with resemblyzer.
        """
        if self.raw_audio_buffer:
            return np.concatenate(self.raw_audio_buffer)
        return None

    def clear_audio_buffer(self):
        """Clear the raw audio buffer for next recording session."""
        self.raw_audio_buffer = []

    def hearing_thread(self, stop_event=None):
        if stop_event is None:
            stop_event = threading.Event()
        return threading.Thread(target=self.listen, args=[stop_event])

    def run_hearing(self):
        self.clear_audio_buffer()
        hearing_thread = self.hearing_thread()
        hearing_thread.start()
        hearing_thread.join()


if __name__ == "__main__":
    hearing = Hearing(verbose=True)
    hearing.words = '["show group one", "show group two", "show group three", "done gigi"]'
    hearing.run_hearing()
    print(hearing.texts)
    print('Done!')