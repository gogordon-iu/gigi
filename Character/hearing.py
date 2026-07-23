from hearingDefinitions import *
import sounddevice as sd
import threading
import json
import webrtcvad
import numpy as np
import platform

try:
    import jax
except ImportError:
    pass

language_models = None

# ── Backend selection ─────────────────────────────────────────────────────────
# On Windows:  use faster-whisper (CPU, int8)
# On OrangePi (Linux/aarch64): use SenseVoiceSmall-RKNN2 (NPU)
IS_WINDOWS = platform.system() == "Windows"
IS_RKNN_PLATFORM = (platform.system() == "Linux" and platform.machine() in ("aarch64", "armv7l"))

HEARING_OPTION = "whisper"  # "whisper" | "sr" | "vosk"

if HEARING_OPTION == "sr":
    import speech_recognition as sr

elif HEARING_OPTION == "whisper":
    import queue
    import time
    from hearingDefinitions import (
        INPUT_SAMPLE_RATE, TARGET_SAMPLE_RATE, SILENCE_DURATION,
        NO_SPEECH_THRESHOLD, VAD_FILTER, REPETITION_PENALTY,
        BEAM_SIZE, BEST_OF
    )

    # ── Try loading RKNNLite dependencies ──
    _rknn_available = False
    import os
    _hearing_dir = os.path.dirname(os.path.abspath(__file__))
    _resources_dir = os.path.abspath(os.path.join(_hearing_dir, "..", "Resources"))
    RKNN_MODEL_PATH = os.path.join(_resources_dir, "sense-voice-encoder.rknn")
    SPEECH_SCALE = 1.0

    try:
        import logging
        _orig_nameToLevel = dict(logging._nameToLevel)
        _orig_levelToName = dict(logging._levelToName)
        from rknnlite.api import RKNNLite
        logging._nameToLevel.update(_orig_nameToLevel)
        logging._levelToName.update(_orig_levelToName)
        import kaldi_native_fbank as knf
        _rknn_available = True
    except ImportError:
        _rknn_available = False

    class SenseVoiceRKNNTranscriber:
        """
        Wraps the SenseVoiceSmall-RKNN2 model for local NPU inference.
        Provides a single `transcribe(audio_float16k) -> str` method.
        """
        def __init__(self, model_path=RKNN_MODEL_PATH):
            import logging
            _orig_nameToLevel = dict(logging._nameToLevel)
            _orig_levelToName = dict(logging._levelToName)
            from rknnlite.api import RKNNLite
            logging._nameToLevel.update(_orig_nameToLevel)
            logging._levelToName.update(_orig_levelToName)
            self.rknn = RKNNLite()
            ret = self.rknn.load_rknn(model_path)
            if ret != 0:
                raise RuntimeError(f"Failed to load RKNN model from {model_path} (code {ret})")
            ret = self.rknn.init_runtime()
            if ret != 0:
                raise RuntimeError(f"Failed to init RKNN runtime (code {ret})")
            print(f"[Hearing] SenseVoiceSmall-RKNN2 loaded from {model_path}")

            # Load CMVN normalization stats
            cmvn_path = os.path.join(_resources_dir, "am.mvn")
            self.cmvn = self.load_cmvn(cmvn_path)

            # Load speaker / query embeddings
            embedding_path = os.path.join(_resources_dir, "embedding.npy")
            self.embedding = np.load(embedding_path)

        def load_cmvn(self, cmvn_file: str) -> np.ndarray:
            with open(cmvn_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            means_list = []
            vars_list = []
            for i in range(len(lines)):
                line_item = lines[i].split()
                if len(line_item) == 0:
                    continue
                if line_item[0] == "<AddShift>":
                    line_item = lines[i + 1].split()
                    if line_item[0] == "<LearnRateCoef>":
                        add_shift_line = line_item[3 : (len(line_item) - 1)]
                        means_list = list(add_shift_line)
                elif line_item[0] == "<Rescale>":
                    line_item = lines[i + 1].split()
                    if line_item[0] == "<LearnRateCoef>":
                        rescale_line = line_item[3 : (len(line_item) - 1)]
                        vars_list = list(rescale_line)
            means = np.array(means_list).astype(np.float64)
            vars = np.array(vars_list).astype(np.float64)
            return np.array([means, vars])

        def apply_lfr(self, inputs: np.ndarray, lfr_m=7, lfr_n=6) -> np.ndarray:
            LFR_inputs = []
            T = inputs.shape[0]
            T_lfr = int(np.ceil(T / lfr_n))
            left_padding = np.tile(inputs[0], ((lfr_m - 1) // 2, 1))
            inputs = np.vstack((left_padding, inputs))
            T = T + (lfr_m - 1) // 2
            for i in range(T_lfr):
                if lfr_m <= T - i * lfr_n:
                    LFR_inputs.append((inputs[i * lfr_n : i * lfr_n + lfr_m]).reshape(1, -1))
                else:
                    num_padding = lfr_m - (T - i * lfr_n)
                    frame = inputs[i * lfr_n :].reshape(-1)
                    for _ in range(num_padding):
                        frame = np.hstack((frame, inputs[-1]))
                    LFR_inputs.append(frame)
            return np.vstack(LFR_inputs).astype(np.float32)

        def apply_cmvn(self, inputs: np.ndarray) -> np.ndarray:
            frame, dim = inputs.shape
            means = np.tile(self.cmvn[0:1, :dim], (frame, 1))
            vars = np.tile(self.cmvn[1:2, :dim], (frame, 1))
            return (inputs + means) * vars

        def _extract_fbank(self, audio_float: np.ndarray) -> np.ndarray:
            """Extract 80-dim log-Mel filterbank features at 16 kHz."""
            import kaldi_native_fbank as knf
            opts = knf.FbankOptions()
            opts.frame_opts.samp_freq = 16000
            opts.frame_opts.dither = 0.0
            opts.frame_opts.window_type = "hamming"
            opts.frame_opts.frame_shift_ms = 10.0
            opts.frame_opts.frame_length_ms = 25.0
            opts.mel_opts.num_bins = 80
            opts.energy_floor = 0
            opts.frame_opts.snip_edges = True
            opts.mel_opts.debug_mel = False
            
            fbank = knf.OnlineFbank(opts)
            # kaldi_native_fbank expects int16-scaled floats
            samples = (audio_float * 32768.0).astype(np.float32)
            fbank.accept_waveform(16000, samples.tolist())
            fbank.input_finished()
            frames = [fbank.get_frame(i) for i in range(fbank.num_frames_ready)]
            if not frames:
                return np.zeros((1, 80), dtype=np.float32)
            return np.array(frames, dtype=np.float32)  # (T, 80)

        def transcribe(self, audio_float: np.ndarray, language: str = "en") -> str:
            """Run NPU inference on a float32 audio chunk (16 kHz, mono)."""
            try:
                # 1. Extract raw fbank
                fbank = self._extract_fbank(audio_float)          # (T, 80)
                if len(fbank) == 0 or (len(fbank) == 1 and np.all(fbank == 0)):
                    return ""

                # 2. Apply LFR (downsampling / stacking)
                lfr_feat = self.apply_lfr(fbank, 7, 6)             # (T', 560)

                # 3. Apply CMVN
                normalized_feat = self.apply_cmvn(lfr_feat)       # (T', 560)

                # 4. Form language, emotion/event (1, 2), text norm (15) query embeddings
                # Map language string to index in embedding.npy: zh=0, en=1, yue=2, ja=3, ko=4
                lang_map = {
                    "zh": 0,
                    "en": 1,
                    "yue": 2,
                    "ja": 3,
                    "ko": 4
                }
                lang_idx = lang_map.get(language, 1) # default to English (1)
                language_query = self.embedding[[[lang_idx]]]       # (1, 1, 560)
                event_emo_query = self.embedding[[[1, 2]]]         # (1, 2, 560)
                text_norm_query = self.embedding[[[15]]]           # (1, 1, 560)
                speech = normalized_feat[np.newaxis, :, :]         # (1, T', 560)

                # Concatenate query embeddings with speech features
                input_content = np.concatenate([
                    language_query,
                    event_emo_query,
                    text_norm_query,
                    speech
                ], axis=1).astype(np.float32)

                # Pad or truncate to RKNN static shape (171 frames)
                RKNN_INPUT_LEN = 171
                T_cat = input_content.shape[1]
                if T_cat < RKNN_INPUT_LEN:
                    input_content = np.pad(input_content, ((0, 0), (0, RKNN_INPUT_LEN - T_cat), (0, 0)))
                else:
                    input_content = input_content[:, :RKNN_INPUT_LEN, :]

                # 5. Run NPU inference
                outputs = self.rknn.inference(inputs=[input_content])
                if outputs is None or len(outputs) == 0:
                    return ""
                logits = outputs[0][0]                             # (25055, 171)

                # 6. Decode output token IDs along axis 0
                token_ids = np.argmax(logits, axis=0).tolist()
                prev = None
                decoded = []
                for tid in token_ids:
                    if tid != 0 and tid != prev:
                        decoded.append(tid)
                    prev = tid
                try:
                    import sentencepiece as spm
                    sp = spm.SentencePieceProcessor()
                    sp.Load(os.path.join(_resources_dir, "chn_jpn_yue_eng_ko_spectok.bpe.model"))
                    text = sp.Decode(decoded)
                    # Clean tags like <|en|>, <|SAD|>, etc.
                    import re
                    text = re.sub(r'<\|.*?\|>', '', text).strip()
                    
                    # Normalize smart quotes and filter out non-ASCII/foreign characters
                    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
                    text = "".join(c for c in text if ord(c) < 128).strip()
                except Exception:
                    text = " ".join(str(t) for t in decoded)
                return text
            except Exception as e:
                print(f"[Hearing] RKNN inference error: {e}")
                return ""

        def release(self):
            self.rknn.release()

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
        from characterDefinitions import USE_NPU_TRANSCRIPTION, USE_NPU_PRONUNCIATION
        self.verbose = verbose
        self.recognizer = None
        self.words = None
        self.texts = []
        self.mic_index = self.get_usb_microphone()

        # Buffer to store raw audio for speaker recognition
        self.raw_audio_buffer = []

        # Pronunciation mode settings
        self.pronunciation_mode = False
        self.pronunciation_grammar = []
        self.vosk_model = None
        self.citrinet_gop = None
        self.use_citrinet_gop = USE_NPU_PRONUNCIATION
        self.pronunciation_engine = 'vosk'
        self.stream_lock = threading.Lock()

        if HEARING_OPTION == "sr":
            self.recognizer = sr.Recognizer()
        elif HEARING_OPTION == "whisper":
            if USE_NPU_TRANSCRIPTION and _rknn_available:
                # ── OrangePi: NPU-accelerated SenseVoiceSmall ─────────────────
                self.model = SenseVoiceRKNNTranscriber()
                self.use_rknn = True
                # RKNN backend handles its own audio processing; still need VAD
                self.vad = webrtcvad.Vad(2)
                self.vad_frame_duration = 30
                self.vad_frame_size = int(TARGET_SAMPLE_RATE * self.vad_frame_duration / 1000)
                self.speech_threshold = 0.10
                self.last_vad_speech_time = None
                self.last_segment_words = []
                self.audio_queue = queue.Queue(maxsize=5)
                # Lightweight audio buffer (no WhisperAudioProcessor needed)
                self._raw_buffer = []
                self._raw_buf_duration = 2.0  # seconds of audio to accumulate before transcribing
            else:
                # ── Windows / CPU: faster-whisper ─────────────────────────────
                from faster_whisper import WhisperModel
                from whisper_helper import WhisperAudioProcessor
                self.use_rknn = False
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
                self.vad = webrtcvad.Vad(2)  # Aggressiveness level 2
                self.vad_frame_duration = 30  # ms (10, 20, or 30)
                self.vad_frame_size = int(TARGET_SAMPLE_RATE * self.vad_frame_duration / 1000)
                self.speech_threshold = 0.10

                # Single VAD-driven silence timer
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

    def load_vosk_model(self):
        if self.vosk_model is None:
            from vosk import Model
            import os
            _hearing_dir = os.path.dirname(os.path.abspath(__file__))
            _resources_dir = os.path.abspath(os.path.join(_hearing_dir, "..", "Resources"))
            vosk_path = os.path.join(_resources_dir, "vosk-model-small-en-us-0.15")
            print(f"[Hearing] Loading Vosk model from {vosk_path}...")
            self.vosk_model = Model(vosk_path)
            print("[Hearing] Vosk model loaded successfully.")

    def load_citrinet_gop(self):
        if self.citrinet_gop is None:
            try:
                import sys
                _char_dir = os.path.dirname(os.path.abspath(__file__))
                if _char_dir not in sys.path:
                    sys.path.append(_char_dir)
                from citrinet_gop import CitrinetGOP
                self.citrinet_gop = CitrinetGOP()
            except Exception as e:
                print(f"[Hearing] Failed to load CitrinetGOP: {e}")

    def get_usb_microphone(self):
        devices = sd.query_devices()
        usb_devices = [
            i for i, device in enumerate(devices)
            if device['max_input_channels'] > 0 and "USB" in device["name"]
        ]
        if len(usb_devices) > 0:
            return usb_devices[0]
        return None

    def _open_input_stream(self, callback):
        """
        Attempt to open a sounddevice InputStream.
        First tries with self.mic_index, and falls back to None (default device) if it fails.
        """
        import time
        time.sleep(0.15)
        with self.stream_lock:
            stream = None
            try:
                print(f"[Hearing] Attempting to open sd.InputStream with mic_index={self.mic_index}...")
                stream = sd.InputStream(
                    samplerate=INPUT_SAMPLE_RATE,
                    channels=1,
                    device=self.mic_index,
                    callback=callback,
                    blocksize=8192,
                    dtype='int16'
                )
                print(f"[Hearing] Successfully opened InputStream on device {self.mic_index}.")
            except Exception as e:
                print(f"[Hearing] Failed to open InputStream with mic_index={self.mic_index}: {e}")
                if self.mic_index is not None:
                    print("[Hearing] Retrying with default device index (None)...")
                    try:
                        stream = sd.InputStream(
                            samplerate=INPUT_SAMPLE_RATE,
                            channels=1,
                            device=None,
                            callback=callback,
                            blocksize=8192,
                            dtype='int16'
                        )
                        print("[Hearing] Successfully opened InputStream on default device.")
                    except Exception as e2:
                        print(f"[Hearing] Failed to open InputStream on default device: {e2}")
                        import traceback
                        traceback.print_exc()
                else:
                    import traceback
                    traceback.print_exc()
            return stream

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
        Transcribe audio, routing to either:
          - SenseVoiceSmall-RKNN2 (OrangePi NPU)
          - faster-whisper (Windows / CPU fallback)
        Applies word-level deduplication and hallucination guard on both paths.
        """
        if len(audio_float) < 8000:  # Skip clips shorter than ~0.5s at 16kHz
            return ""

        if getattr(self, 'pronunciation_mode', False):
            is_citrinet_engine = (getattr(self, 'pronunciation_engine', 'vosk') == 'citrinet')
            if is_citrinet_engine and getattr(self, 'use_citrinet_gop', True):
                self.load_citrinet_gop()
            
            if is_citrinet_engine and getattr(self, 'citrinet_gop', None) is not None and not self.citrinet_gop.use_mock:
                # Bypass Vosk chunk-by-chunk decoding to use the real NPU Citrinet GOP pipeline.
                # Falling through to the standard ASR (Whisper/SenseVoice) so self.texts is populated.
                pass
            else:
                # Fallback to Vosk if Citrinet NPU is not available or running in mock or engine is vosk
                try:
                    self.load_vosk_model()
                    from vosk import KaldiRecognizer
                    import re
                    
                    grammar_list = [w.lower().replace("’", "'") for w in getattr(self, 'pronunciation_grammar', []) if w]
                    grammar_list = [re.sub(r"[^\w']", "", w) for w in grammar_list]
                    grammar_list = [w for w in grammar_list if w]
                    
                    if "[unk]" not in grammar_list:
                        grammar_list.append("[unk]")
                    
                    grammar_json = json.dumps(grammar_list)
                    rec = KaldiRecognizer(self.vosk_model, 16000, grammar_json)
                    
                    audio_int16 = (audio_float * 32767.0).astype(np.int16)
                    rec.AcceptWaveform(audio_int16.tobytes())
                    result_json = json.loads(rec.FinalResult())
                    text = result_json.get("text", "")
                    
                    if self.verbose:
                        print(f"[Vosk Pronunciation] Grammar: {grammar_json} -> Result: '{text}'")
                    return text
                except Exception as e:
                    print(f"[Vosk Pronunciation] Error: {e}")

        if getattr(self, 'use_rknn', False):
            # ── RKNN path ─────────────────────────────────────────────────────
            try:
                result = self.model.transcribe(audio_float, language=language)
                if not result:
                    return ""
                current_words = result.strip().split()
                unique_words = self.remove_duplicate_words(current_words)
                if not unique_words:
                    return ""
                result = " ".join(unique_words)
                if self._is_hallucination(result):
                    if self.verbose:
                        print("[RKNN] Hallucination detected, discarding.")
                    return ""
                return result
            except Exception as e:
                if self.verbose:
                    print(f"[RKNN] Transcription error: {e}")
                return ""
        else:
            # ── faster-whisper path ───────────────────────────────────────────
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
        if getattr(self, 'face', None):
            self.face.feedback_state = "listening"
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

            stream = self._open_input_stream(self.audio_callback_optimized)
            if stream is None:
                print("[Hearing] Failed to initialize microphone. Exiting listen.")
                return

            with stream:
                print("Listening... Speak into the microphone.")

                while True:
                    if stop_event and stop_event.is_set():
                        break
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
                if stop_event and stop_event.is_set():
                    break
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
        if getattr(self, 'face', None):
            self.face.feedback_state = None

    def audio_callback_optimized(self, indata, frames, time_info, status):
        """
        Audio callback with WebRTC VAD and buffering.
        On faster-whisper path: uses WhisperAudioProcessor.
        On RKNN path: accumulates raw float32 into a rolling buffer.
        Only queues audio chunks that pass the VAD speech check.
        """
        audio_data = indata.flatten().copy()
        if len(audio_data) == 0:
            return

        if getattr(self, 'use_rknn', False):
            # ── RKNN path: simple rolling buffer ─────────────────────────────
            audio_float = audio_data.astype(np.float32) / 32768.0
            self._raw_buffer.append(audio_float)

            # Check how many seconds we have buffered at native sample rate (INPUT_SAMPLE_RATE)
            total_samples = sum(len(c) for c in self._raw_buffer)
            if total_samples >= int(INPUT_SAMPLE_RATE * self._raw_buf_duration):
                audio_chunk_native = np.concatenate(self._raw_buffer)
                self._raw_buffer = []
                
                # Resample native 48 kHz chunk to target 16 kHz
                from whisper_helper import resample_audio
                audio_int16_native = (audio_chunk_native * 32768.0).astype(np.int16)
                audio_int16_resampled = resample_audio(audio_int16_native, INPUT_SAMPLE_RATE, TARGET_SAMPLE_RATE)
                audio_chunk_resampled = audio_int16_resampled.astype(np.float32) / 32768.0
                
                if self.contains_speech(audio_int16_resampled):
                    self.last_vad_speech_time = time.time()
                    try:
                        self.audio_queue.put_nowait(audio_chunk_resampled)
                    except queue.Full:
                        try:
                            self.audio_queue.get_nowait()
                            self.audio_queue.put_nowait(audio_chunk_resampled)
                        except:
                            pass
        else:
            # ── Whisper path: WhisperAudioProcessor ───────────────────────────
            if hasattr(self, 'audio_processor'):
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
        
        def safe_listen(*args, **kwargs):
            try:
                self.listen(*args, **kwargs)
            except Exception as e:
                print(f"[Hearing] Critical exception in listen thread: {e}")
                import traceback
                traceback.print_exc()
                if getattr(self, 'face', None):
                    self.face.feedback_state = None
                    if hasattr(self.face, 'set_reading_status'):
                        self.face.set_reading_status("idle")
                        
        return threading.Thread(target=safe_listen, args=[stop_event])

    def listen_fluid(self, stop_event=None, check_callback=None, n_transcripts=1):
        """
        Similar to listen, but periodically calls check_callback(text) every n_transcripts chunks.
        If the callback returns True, listening stops early.
        """
        if getattr(self, 'face', None):
            self.face.feedback_state = "listening"
            if hasattr(self.face, 'set_reading_status'):
                self.face.set_reading_status("listening")
        if HEARING_OPTION == "sr" or HEARING_OPTION == "vosk":
            self.listen(stop_event)
            if getattr(self, 'face', None):
                self.face.feedback_state = None
                if hasattr(self.face, 'set_reading_status'):
                    self.face.set_reading_status("idle")
            return

        if HEARING_OPTION == "whisper":
            self.audio_queue = queue.Queue()
            self.last_vad_speech_time = None
            text = ""
            chunk_count = 0

            # Reset deduplication state for new listening session
            self.last_segment_words = []

            stream = self._open_input_stream(self.audio_callback_optimized)
            if stream is None:
                print("[Hearing] Failed to initialize microphone. Exiting listen_fluid.")
                return

            with stream:
                print("Fluid Listening... Speak into the microphone.")

                while True:
                    if stop_event and stop_event.is_set():
                        break

                    try:
                        if getattr(self, 'face', None) and hasattr(self.face, 'set_reading_status'):
                            self.face.set_reading_status("listening")
                        audio_float = self.audio_queue.get(timeout=1.0) # GOREN changed to 1.0, it was 0.3
                    except queue.Empty:
                        if (
                            self.last_vad_speech_time is not None
                            and len(text.split()) >= 1
                            and time.time() - self.last_vad_speech_time > SILENCE_DURATION
                        ):
                            print("Silence detected. Stopping transcription.")
                            break
                        continue

                    if getattr(self, 'face', None) and hasattr(self.face, 'set_reading_status'):
                        self.face.set_reading_status("transcribing")
                    self.raw_audio_buffer.append(audio_float)
                    transcription = self.transcribe_with_dedup(audio_float, language="en")

                    if transcription:
                        print(f"Transcription: {transcription}")
                        text += transcription + " "
                        chunk_count += 1
                        
                        if check_callback and chunk_count >= n_transcripts:
                            is_done = check_callback(text.strip())
                            if is_done:
                                print("Fluid listening callback detected 'done'. Stopping.")
                                if stop_event is not None:
                                    stop_event.set()
                                break
                            else:
                                chunk_count = 0

                    if self.verbose:
                        vad_age = time.time() - self.last_vad_speech_time if self.last_vad_speech_time else 0
                        print(f"words: {len(text.split())}, silence: {vad_age:.1f}s")

                if text.strip():
                    self.texts.append(text.strip())

                if stop_event is not None:
                    stop_event.set()
        if getattr(self, 'face', None):
            self.face.feedback_state = None
            if hasattr(self.face, 'set_reading_status'):
                self.face.set_reading_status("idle")

    def hearing_fluid_thread(self, stop_event=None, check_callback=None, n_transcripts=1):
        if stop_event is None:
            stop_event = threading.Event()
            
        def safe_listen_fluid(*args, **kwargs):
            try:
                self.listen_fluid(*args, **kwargs)
            except Exception as e:
                print(f"[Hearing] Critical exception in listen_fluid thread: {e}")
                import traceback
                traceback.print_exc()
                if getattr(self, 'face', None):
                    self.face.feedback_state = None
                    if hasattr(self.face, 'set_reading_status'):
                        self.face.set_reading_status("idle")
                        
        return threading.Thread(target=safe_listen_fluid, args=[stop_event, check_callback, n_transcripts])

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