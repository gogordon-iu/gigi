"""
Helper functions and audio buffering for optimized Faster Whisper integration.
"""

import numpy as np
import logging
from collections import deque
import time
from scipy import signal

logger = logging.getLogger(__name__)


def resample_audio(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Resample audio from original sample rate to target sample rate.
    
    Args:
        audio_data: Audio data as int16 numpy array
        orig_sr: Original sample rate
        target_sr: Target sample rate
    
    Returns:
        Resampled audio as int16 numpy array
    """
    if orig_sr == target_sr:
        return audio_data
    
    num_samples = int(len(audio_data) * target_sr / orig_sr)
    try:
        resampled = signal.resample(audio_data, num_samples)
        return resampled.astype(np.int16)
    except Exception:
        indices = np.linspace(0, len(audio_data) - 1, num_samples)
        return np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.int16)


def clean_transcript(text: str) -> str:
    """Clean and normalize transcript text."""
    if not text:
        return ""
    
    text = ' '.join(text.split())
    artifacts = ['[BLANK_AUDIO]', '[MUSIC]', '[NOISE]', '♪', '♫']
    for artifact in artifacts:
        text = text.replace(artifact, '')
    
    return text.strip()


class WhisperAudioProcessor:
    """Optimized audio buffering and speech detection for Faster Whisper."""
    
    def __init__(
        self,
        native_sample_rate: int = 48000,
        target_sample_rate: int = 16000,
        energy_threshold: float = 500,
        buffer_duration: float = 3.0,
        min_audio_length: float = 1.0,
        silence_duration: float = 1.0,
        debug: bool = False,
    ):
        self.native_sample_rate = native_sample_rate
        self.target_sample_rate = target_sample_rate
        self.energy_threshold = energy_threshold
        self.buffer_duration = buffer_duration
        self.min_audio_length = min_audio_length
        self.silence_duration = silence_duration
        self.debug = debug
        
        self.audio_buffer = deque()
        self.last_speech_time = time.time()
    
    def get_audio_energy(self, audio_data: np.ndarray) -> float:
        """Calculate RMS energy of audio data."""
        if len(audio_data) == 0:
            return 0.0
        audio_clipped = np.clip(audio_data, -32768, 32767)
        energy = np.sqrt(np.mean(audio_clipped.astype(np.float64) ** 2))
        return float(energy) if not np.isnan(energy) else 0.0
    
    def has_speech(self, audio_data: np.ndarray) -> bool:
        """Simple energy-based speech detection."""
        return self.get_audio_energy(audio_data) > self.energy_threshold
    
    def should_process_buffer(self) -> bool:
        """Check if buffer has reached capacity or speech followed by silence."""
        current_time = time.time()
        buf_duration = len(self.audio_buffer) / self.native_sample_rate
        silence_dur = current_time - self.last_speech_time
        
        return (
            buf_duration >= self.buffer_duration
            or (buf_duration >= self.min_audio_length and silence_dur >= self.silence_duration)
        )
    
    def add_to_buffer(self, audio_chunk: np.ndarray):
        """Add audio chunk to buffer and update speech time."""
        self.audio_buffer.extend(audio_chunk)
        if self.has_speech(audio_chunk):
            self.last_speech_time = time.time()
    
    def get_buffered_audio(self):
        """Get buffered audio as float32 array normalized for Whisper (resampled to 16 kHz)."""
        if len(self.audio_buffer) == 0:
            return None
        
        audio_chunk = np.array(list(self.audio_buffer), dtype=np.int16)
        if self.get_audio_energy(audio_chunk) > self.energy_threshold * 0.1:
            if self.native_sample_rate != self.target_sample_rate:
                audio_chunk = resample_audio(audio_chunk, self.native_sample_rate, self.target_sample_rate)
            
            audio_float = audio_chunk.astype(np.float32) / 32768.0
            audio_float = np.clip(audio_float, -1.0, 1.0)
            self.audio_buffer.clear()
            return audio_float
        
        self.audio_buffer.clear()
        return None
    
    def clear_buffer(self):
        """Clear the audio buffer."""
        self.audio_buffer.clear()


def transcribe_optimized(model, audio_chunk: np.ndarray, language: str = "en", debug: bool = False) -> str:
    """Optimized transcription with Faster Whisper."""
    if len(audio_chunk) < 8000:
        return ""
    
    try:
        segments, info = model.transcribe(
            audio_chunk,
            beam_size=5,
            language=language,
            condition_on_previous_text=False,
            word_timestamps=False,
            vad_filter=True,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            temperature=0.0,
        )
        
        transcript_parts = []
        for segment in segments:
            text = clean_transcript(segment.text)
            if text:
                transcript_parts.append(text)
        
        return " ".join(transcript_parts) if transcript_parts else ""
    except Exception as e:
        if debug:
            logger.error(f"Transcription error: {e}")
        return ""


def calibrate_energy_threshold(stream, native_sample_rate: int, chunk_size: int, duration: float = 3.0, debug: bool = False) -> float:
    """Calibrate energy threshold based on ambient background noise."""
    logger.info(f"Calibrating audio input for {duration} seconds...")
    max_energy = 0.0
    num_chunks = int(duration * native_sample_rate / chunk_size)
    
    for _ in range(num_chunks):
        data = stream.read(chunk_size, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_data.astype(np.float64) ** 2))
        if not np.isnan(energy):
            max_energy = max(max_energy, float(energy))
            if debug:
                print(f"Audio energy: {energy:.2f} (max: {max_energy:.2f})", end='\r')
    
    if debug:
        print(f"\nMax energy detected: {max_energy:.2f}")
    
    if max_energy < 100:
        suggested_threshold = max(50.0, max_energy * 0.8)
    else:
        suggested_threshold = max_energy * 0.3
    
    logger.info(f"Suggested energy threshold: {suggested_threshold:.2f}")
    return suggested_threshold
