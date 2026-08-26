import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import time
import json
import random
import threading
import builtins
import shutil
import numpy as np
import sounddevice as sd
import soundfile as sf

# Resolve paths to import Gigi modules correctly
gigi_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, gigi_dir)
sys.path.insert(0, os.path.join(gigi_dir, "Character"))

from Character.character import Character
from Character.hearing import Hearing
from Character.hearingDefinitions import INPUT_SAMPLE_RATE
from Demo.reading_fluency import play_reading_fluency

class MockInputStream:
    """
    Simulates a sounddevice InputStream by feeding a WAV file chunk-by-chunk in real-time,
    and optionally playing the audio out loud through the speaker.
    """
    def __init__(self, wav_path, callback, blocksize=8192, samplerate=INPUT_SAMPLE_RATE, play_out_loud=False):
        self.wav_path = wav_path
        self.callback = callback
        self.blocksize = blocksize
        self.samplerate = samplerate
        self.play_out_loud = play_out_loud
        self.stop_event = threading.Event()
        self.thread = None

    def __enter__(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)

    def _run(self):
        # Load the wav file
        data, fs = sf.read(self.wav_path)
        
        # Keep channel 1 (mono) if stereo
        if len(data.shape) > 1:
            data = data[:, 0]

        # Resample dynamically if sample rate doesn't match target samplerate (16000 Hz)
        if fs != self.samplerate:
            duration = len(data) / fs
            num_samples = int(duration * self.samplerate)
            data = np.interp(
                np.linspace(0, len(data), num_samples, endpoint=False),
                np.arange(len(data)),
                data
            )
            fs = self.samplerate

        # Convert back to standard int16 PCM format for Vosk
        data_int16 = (data * 32767.0).astype(np.int16)

        # Play the audio out loud asynchronously
        if self.play_out_loud:
            import pygame
            try:
                sound = pygame.mixer.Sound(self.wav_path)
                sound.play()
            except Exception as e:
                print(f"[Mock Stream] Pygame play warning: {e}. Trying sounddevice...")
                try:
                    sd.play(data, fs)
                except Exception:
                    pass

        # Stream chunks to ASR callback at real-time speeds
        chunk_duration = self.blocksize / self.samplerate
        idx = 0
        while idx < len(data_int16) and not self.stop_event.is_set():
            chunk = data_int16[idx : idx + self.blocksize]
            if len(chunk) < self.blocksize:
                pad = np.zeros(self.blocksize - len(chunk), dtype=np.int16)
                chunk = np.concatenate([chunk, pad])
            
            # sounddevice callback receives 2D array of (blocksize, channels)
            chunk_2d = chunk.reshape(-1, 1)
            
            try:
                self.callback(chunk_2d, self.blocksize, None, None)
            except Exception as e:
                print(f"[Mock Stream] Callback error: {e}")
                
            idx += self.blocksize
            time.sleep(chunk_duration)


def generate_test_wav(gigi, text, filename):
    """Generates synthetic speech for the given text using the NixTTS model on the robot."""
    test_audio_dir = os.path.join(gigi_dir, "Assets", "ReadingFluency", "test_audio")
    os.makedirs(test_audio_dir, exist_ok=True)
    out_path = os.path.join(test_audio_dir, filename)
    
    print(f"[Test Helper] Rendering TTS for '{text}' -> {out_path}")
    
    try:
        gen_file = gigi.speech.generate_speech_text(text=text)
        wav, orig_sr = sf.read(gen_file)
        if len(wav.shape) > 1:
            wav = wav[:, 0]
        wav = wav.astype(np.float32)
    except Exception as e:
        print(f"[Test Helper] Warning: TTS generation failed: {e}. Using dummy audio.")
        wav = np.zeros(INPUT_SAMPLE_RATE * 2, dtype=np.float32)
        orig_sr = INPUT_SAMPLE_RATE
        
    # Resample to INPUT_SAMPLE_RATE for callback compatibility
    target_sr = INPUT_SAMPLE_RATE
    if orig_sr != target_sr:
        duration = len(wav) / orig_sr
        num_samples = int(duration * target_sr)
        wav_16k = np.interp(
            np.linspace(0, len(wav), num_samples, endpoint=False),
            np.arange(len(wav)),
            wav
        )
    else:
        wav_16k = wav
    
    # Ensure minimum duration of 2.0s to allow ASR buffer processing
    min_samples = int(2.0 * target_sr)
    if len(wav_16k) < min_samples:
        pad_len = min_samples - len(wav_16k)
        wav_16k = np.concatenate([wav_16k, np.zeros(pad_len, dtype=np.float32)])
        
    # Save as 16-bit PCM WAV
    sf.write(out_path, wav_16k, target_sr, subtype='PCM_16')
    return out_path


class TestReadingFluencyIntegration(unittest.TestCase):
    gigi = None
    wav_paths = {}
    test_wav_files = []

    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Test Character and NixTTS Models ===")
        # Re-use a single Character instance to speed up NPU/Nix initialization
        cls.gigi = Character(character_name="fuzzy", wakeup=True, activity="ReadingFluency")
        
        # Generate the standard correct/incorrect WAV sequences we need for tests
        cls.wav_paths["stars"] = generate_test_wav(cls.gigi, "stars", "stars.wav")
        cls.wav_paths["correct_sentence"] = generate_test_wav(
            cls.gigi, "when you look up at the sky at night what do you see", "correct_sentence.wav"
        )
        cls.wav_paths["incorrect_sentence"] = generate_test_wav(
            cls.gigi, "when you look up at the green at night what do you see", "incorrect_sentence.wav"
        )
        cls.wav_paths["correct_word"] = generate_test_wav(cls.gigi, "sky", "correct_word.wav")
        cls.wav_paths["incorrect_word"] = generate_test_wav(cls.gigi, "green", "incorrect_word.wav")
        cls.wav_paths["remainder_sentence"] = generate_test_wav(
            cls.gigi, "at night what do you see", "remainder_sentence.wav"
        )
        cls.wav_paths["start_second_word_sentence"] = generate_test_wav(
            cls.gigi, "you look up at the sky at night what do you see", "start_second_word_sentence.wav"
        )
        cls.wav_paths["syllable_sounding_sentence"] = generate_test_wav(
            cls.gigi, "when you look up at the sk sky at night what do you see", "syllable_sounding_sentence.wav"
        )
        # 5.5 seconds pure silence WAV for silence coaxing / advance tests
        silence_audio_dir = os.path.join(gigi_dir, "Assets", "ReadingFluency", "test_audio")
        silence_path = os.path.join(silence_audio_dir, "silence_5s.wav")
        silence_data = np.zeros(int(INPUT_SAMPLE_RATE * 5.5), dtype=np.float32)
        sf.write(silence_path, silence_data, INPUT_SAMPLE_RATE, subtype='PCM_16')
        cls.wav_paths["silence_5s"] = silence_path

    def setUp(self):
        # Clear out queue for each test
        self.test_wav_files.clear()
        
        # Mock face recognition to automatically log in as Goren
        self.gigi.vision = MagicMock()
        self.gigi.vision.running = True
        self.gigi.vision.face_cache.get_all_faces.return_value = {
            "1": {"name": "Goren", "recognition_attempted": True}
        }
        self.gigi.vision.get_latest_frame.return_value = None
        self.gigi.vision.get_last_data.return_value = {}
        
        # Prevent stop_character from destroying class-level static components
        self.gigi.stop_character = MagicMock()
        
        # Reset word bank config
        if hasattr(self.gigi, 'logger'):
            # Reset logger initialized status to force fresh directories
            self.gigi.logger.is_initialized = False

        # Start patching Character in Demo.reading_fluency to reuse cls.gigi
        self.char_patcher = patch('Demo.reading_fluency.Character', return_value=self.gigi)
        self.char_patcher.start()

        # Monkeypatch the actual bound method on the instance to avoid import path differences
        import types
        self.original_open_input_stream = self.gigi.hearing._open_input_stream
        self.gigi.hearing._open_input_stream = types.MethodType(
            lambda inst, cb: self.mock_open_input_stream(cb),
            self.gigi.hearing
        )
        
        # Bypass WebRTC VAD during tests to ensure synthetic audio is always processed
        self.original_contains_speech = self.gigi.hearing.contains_speech
        self.gigi.hearing.contains_speech = MagicMock(return_value=True)

        # Mock transcription function to bypass chunk boundaries and keep tests deterministic
        self.current_transcription = ""
        self._already_transcribed = False
        self.original_transcribe = self.gigi.hearing.transcribe_with_dedup
        
        def mock_transcribe(audio_float, language="en"):
            if self._already_transcribed:
                return ""
            self._already_transcribed = True
            return self.current_transcription
            
        self.gigi.hearing.transcribe_with_dedup = mock_transcribe

    def tearDown(self):
        # Restore original transcriber
        if hasattr(self, 'original_transcribe'):
            self.gigi.hearing.transcribe_with_dedup = self.original_transcribe

        # Restore original VAD checker
        if hasattr(self, 'original_contains_speech'):
            self.gigi.hearing.contains_speech = self.original_contains_speech
            
        # Restore original bound method
        if hasattr(self, 'original_open_input_stream'):
            self.gigi.hearing._open_input_stream = self.original_open_input_stream

        # Stop Character patching
        self.char_patcher.stop()
        
        # Reset word bank files and state
        if hasattr(self.gigi, 'logger') and self.gigi.logger.session_dir:
            user_dir = os.path.dirname(self.gigi.logger.session_dir)
            word_bank_file = os.path.join(user_dir, "word_bank.json")
            if os.path.exists(word_bank_file):
                try:
                    os.remove(word_bank_file)
                except Exception:
                    pass

    def mock_open_input_stream(self, callback):
        """Intercepts sounddevice InputStream and feeds our test WAV files in order."""
        if self.test_wav_files:
            wav_path = self.test_wav_files.pop(0)
            filename = os.path.basename(wav_path)
            print(f"[Test Integration] Injecting WAV file: '{filename}'")
            
            # Map filename to expected transcription
            if filename == "correct_sentence.wav":
                self.current_transcription = "when you look up at the sky at night what do you see"
            elif filename == "incorrect_sentence.wav":
                self.current_transcription = "when you look up at the green at night what do you see"
            elif filename == "correct_word.wav":
                self.current_transcription = "sky"
            elif filename == "incorrect_word.wav":
                self.current_transcription = "green"
            elif filename == "stars.wav":
                self.current_transcription = "stars"
            elif filename == "remainder_sentence.wav":
                self.current_transcription = "at night what do you see"
            elif filename == "start_second_word_sentence.wav":
                self.current_transcription = "you look up at the sky at night what do you see"
            else:
                self.current_transcription = ""
                
            self._already_transcribed = False
            return MockInputStream(wav_path, callback)
        else:
            print("[Test Integration] No test WAV files left in queue. Returning empty dummy stream.")
            # Return a dummy context manager to prevent crash
            class DummyStream:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return DummyStream()

    def get_word_bank(self):
        if not hasattr(self.gigi, 'logger') or not self.gigi.logger.session_dir:
            self.fail("Logging session was not initialized. The activity probably failed/crashed early.")
        user_dir = os.path.dirname(self.gigi.logger.session_dir)
        word_bank_file = os.path.join(user_dir, "word_bank.json")
        self.assertTrue(os.path.exists(word_bank_file), "word_bank.json was not created.")
        with open(word_bank_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_correct_reading_flow(self):
        """Test Case 1: User chooses 'stars' and reads the first sentence correctly."""
        # Wave Queue:
        # 1. First Sentence: correct sentence
        self.test_wav_files = [self.wav_paths["correct_sentence"]]

        original_open_file = builtins.open

        # Mock passage file to contain only the first sentence to end the test early
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            # Run the actual reading fluency activity bypassing hello and selection
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False)

        # Assertions
        bank = self.get_word_bank()
        self.assertEqual(bank.get("sky"), "correct")

    def test_correction_success_flow(self):
        """Test Case 2: User makes a mistake on 'sky', then successfully corrects it."""
        # Wave Queue:
        # 1. First Sentence: incorrect sentence ("sky" -> "green")
        # 2. Single Word Correction: correct word ("sky")
        # 3. Sentence re-read: correct sentence
        self.test_wav_files = [
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["correct_word"],
            self.wav_paths["correct_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        # Assertions: Verify word bank updated from 'incorrect' to 'correct'
        bank = self.get_word_bank()
        self.assertEqual(bank.get("sky"), "correct")

    def test_correction_failure_flow(self):
        """Test Case 3: User makes a mistake, fails to correct it, and Gigi moves past."""
        # Wave Queue:
        # 1. First Sentence: incorrect sentence ("sky" -> "green")
        # 2. Single Word Correction: incorrect word ("green")
        # 3. Sentence Continuation: remainder sentence ("at night what do you see")
        self.test_wav_files = [
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["incorrect_word"],
            self.wav_paths["remainder_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        # Assertions: Verify word is marked as 'incorrect' in word bank
        bank = self.get_word_bank()
        self.assertEqual(bank.get("sky"), "incorrect")

    def test_three_strikes_restores_fluency(self):
        """Test Case 4: 3 repeat mistakes cause Gigi to ask to read from beginning without corrections."""
        # Wave Queue:
        # 1. Sentence Read 1: incorrect sentence (mistake on "sky", corrections = 1)
        # 2. Correction 1: correct word (success! resets sentence progress to 0)
        # 3. Sentence Read 2: incorrect sentence (mistake on "sky", corrections = 2)
        # 4. Correction 2: correct word (success! resets sentence progress to 0)
        # 5. Sentence Read 3: incorrect sentence (3rd correction reached! sets no_more_corrections_for_sentence = True and resets to 0)
        # 6. Final Sentence Read: incorrect sentence (ignored because no_more_corrections_for_sentence is True, moves past sentence)
        self.test_wav_files = [
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["correct_word"],
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["correct_word"],
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["incorrect_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        # Assertions: Verify the activity finished cleanly
        bank = self.get_word_bank()
        self.assertIsNotNone(bank)

    def test_probabilistic_short_word_skip(self):
        """Test Case 5: Short word error is auto-passed when random roll exceeds probability."""
        # Wave Queue:
        # 1. First Sentence: incorrect sentence ("sky" -> "green")
        # 2. Sentence Continuation: remainder sentence ("at night what do you see")
        # Since random.random is mocked to 0.99 (>= 0.20 probability), Gigi skips re-reading and continues!
        self.test_wav_files = [
            self.wav_paths["incorrect_sentence"],
            self.wav_paths["remainder_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open), patch('random.random', return_value=0.99):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=False)

        bank = self.get_word_bank()
        # Word is recorded as incorrect in bank, but session completed without prompting correction
        self.assertEqual(bank.get("sky"), "incorrect")

    def test_start_from_second_word_flow(self):
        """Test Case 6: User starts reading from the 2nd word ('you') instead of 1st word ('when'). Gigi accepts it and finishes cleanly."""
        self.test_wav_files = [
            self.wav_paths["start_second_word_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        bank = self.get_word_bank()
        self.assertEqual(bank.get("when"), "correct")
        self.assertEqual(bank.get("you"), "correct")
        self.assertEqual(bank.get("sky"), "correct")

    def test_silence_coax_and_advance(self):
        """Test Case 7: 1st 5s silence triggers encouragement coax prompt. 2nd 5s silence advances to next sentence."""
        # Wave Queue:
        # 1. 5s silence (triggers coax prompt, remains on sentence 1)
        # 2. 5s silence (triggers 2nd silence -> advances past sentence 1 to sentence 2)
        # 3. Read sentence 2 correctly
        self.test_wav_files = [
            self.wav_paths["silence_5s"],
            self.wav_paths["silence_5s"],
            self.wav_paths["correct_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?\nThe sun is a star.")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        bank = self.get_word_bank()
        self.assertIsNotNone(bank)

    def test_slow_reading_syllable_sounding(self):
        """Test Case 8: User slowly sounds out syllables ('sk sky') before the whole word. Gigi does not interrupt and completes cleanly."""
        self.test_wav_files = [
            self.wav_paths["syllable_sounding_sentence"]
        ]

        original_open_file = builtins.open
        def mock_open(file, *args, **kwargs):
            if "stars_passage.txt" in str(file):
                import io
                return io.StringIO("When you look up at the sky at night, what do you see?")
            return original_open_file(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            play_reading_fluency(show_karaoke=False, run_hello=False, run_selection=False, story_override="stars", run_comprehension=False, force_reread=True)

        bank = self.get_word_bank()
        self.assertEqual(bank.get("sky"), "correct")

if __name__ == "__main__":
    unittest.main()
