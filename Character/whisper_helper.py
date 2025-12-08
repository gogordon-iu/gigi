"""
Helper functions for optimized Faster Whisper integration
"""

import numpy as np
import logging
from collections import deque
import time
from scipy import signal

logger = logging.getLogger(__name__)

class WhisperAudioProcessor:
    """Optimized audio processing for Faster Whisper"""
    
    def __init__(self, native_sample_rate=48000, target_sample_rate=16000, 
                 energy_threshold=500, buffer_duration=3.0, min_audio_length=1.0, 
                 silence_duration=1.0, debug=False):
        """
        Initialize audio processor
        
        Args:
            native_sample_rate: Microphone's native sample rate
            target_sample_rate: Target sample rate for Whisper (16000)
            energy_threshold: Energy threshold for speech detection
            buffer_duration: Maximum buffer duration in seconds
            min_audio_length: Minimum audio length to process
            silence_duration: Silence duration before processing
            debug: Enable debug output
        """
        self.native_sample_rate = native_sample_rate
        self.target_sample_rate = target_sample_rate
        self.energy_threshold = energy_threshold
        self.buffer_duration = buffer_duration
        self.min_audio_length = min_audio_length
        self.silence_duration = silence_duration
        self.debug = debug
        
        # Buffering
        self.audio_buffer = deque()
        self.last_speech_time = time.time()
    
    def get_audio_energy(self, audio_data):
        """Calculate RMS energy of audio data"""
        # Ensure valid data
        if len(audio_data) == 0:
            return 0.0
        # Clip extreme values and calculate energy
        audio_clipped = np.clip(audio_data, -32768, 32767)
        energy = np.sqrt(np.mean(audio_clipped.astype(np.float64)**2))
        return energy if not np.isnan(energy) else 0.0
    
    def has_speech(self, audio_data):
        """Simple energy-based speech detection"""
        energy = self.get_audio_energy(audio_data)
        return energy > self.energy_threshold
    
    def should_process_buffer(self):
        """Check if buffer should be processed"""
        current_time = time.time()
        buffer_duration = len(self.audio_buffer) / self.native_sample_rate
        silence_duration = current_time - self.last_speech_time
        
        return (buffer_duration >= self.buffer_duration or 
                (buffer_duration >= self.min_audio_length and 
                 silence_duration >= self.silence_duration))
    
    def add_to_buffer(self, audio_chunk):
        """Add audio chunk to buffer and update speech time"""
        self.audio_buffer.extend(audio_chunk)
        if self.has_speech(audio_chunk):
            self.last_speech_time = time.time()
    
    def get_buffered_audio(self):
        """Get buffered audio as float32 array for Whisper (resampled to target rate)"""
        if len(self.audio_buffer) == 0:
            return None
        
        # Convert buffer to array
        audio_chunk = np.array(list(self.audio_buffer), dtype=np.int16)
        
        # Check if chunk has enough speech
        if self.get_audio_energy(audio_chunk) > self.energy_threshold * 0.1:
            # Resample to target sample rate if needed
            if self.native_sample_rate != self.target_sample_rate:
                audio_chunk = resample_audio(audio_chunk, self.native_sample_rate, self.target_sample_rate)
            
            # Convert to float32 for Whisper (normalize to [-1.0, 1.0])
            audio_float = audio_chunk.astype(np.float32) / 32768.0
            # Clip to valid range
            audio_float = np.clip(audio_float, -1.0, 1.0)
            self.audio_buffer.clear()
            return audio_float
        
        self.audio_buffer.clear()
        return None
    
    def clear_buffer(self):
        """Clear the audio buffer"""
        self.audio_buffer.clear()


def clean_transcript(text):
    """Clean and normalize transcript text"""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove common transcription artifacts
    artifacts = ['[BLANK_AUDIO]', '[MUSIC]', '[NOISE]', '♪', '♫']
    for artifact in artifacts:
        text = text.replace(artifact, '')
    
    return text.strip()


def resample_audio(audio_data, orig_sr, target_sr):
    """
    Resample audio from original sample rate to target sample rate
    
    Args:
        audio_data: Audio data as int16 numpy array
        orig_sr: Original sample rate
        target_sr: Target sample rate
    
    Returns:
        Resampled audio as int16 numpy array
    """
    if orig_sr == target_sr:
        return audio_data
    
    # [OPTIMIZATION] Fast path for integer downsampling (e.g. 48k -> 16k)
    # This avoids heavy FFT/filtering operations when a simple decimation is sufficient for speech
    if orig_sr > target_sr and orig_sr % target_sr == 0:
        step = orig_sr // target_sr
        return audio_data[::step]
        
    # Calculate number of samples in resampled audio
    num_samples = int(len(audio_data) * target_sr / orig_sr)
    
    # Resample using scipy
    resampled = signal.resample(audio_data, num_samples)
    
    # Convert back to int16
    return resampled.astype(np.int16)


def transcribe_optimized(model, audio_chunk, language="en", debug=False):
    """
    Optimized transcription with Faster Whisper
    
    Args:
        model: WhisperModel instance
        audio_chunk: Audio data as float32 numpy array (must be 16kHz)
        language: Language code or None for auto-detect
        debug: Enable debug output
    
    Returns:
        Transcribed text
    """
    if len(audio_chunk) < 8000:  # Skip very short clips (< 0.5s at 16kHz)
        return ""
    
    try:
        # Transcribe with optimized parameters
        segments, info = model.transcribe(
            audio_chunk,
            beam_size=5,  # Better accuracy than beam_size=1
            language=language,
            condition_on_previous_text=False,
            word_timestamps=False,  # Disabled for speed
            vad_filter=True,  # Let Whisper handle VAD
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            temperature=0.0  # Deterministic output
        )
        
        # Extract and clean transcript
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


def calibrate_energy_threshold(stream, native_sample_rate, chunk_size, duration=3.0, debug=False):
    """
    Calibrate energy threshold based on ambient noise
    
    Args:
        stream: Audio input stream
        native_sample_rate: Native sample rate of the microphone
        chunk_size: Audio chunk size
        duration: Calibration duration in seconds
        debug: Enable debug output
    
    Returns:
        Suggested energy threshold
    """
    logger.info(f"Calibrating audio input for {duration} seconds...")
    
    max_energy = 0
    num_chunks = int(duration * native_sample_rate / chunk_size)
    
    for _ in range(num_chunks):
        data = stream.read(chunk_size, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        energy = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
        if not np.isnan(energy):
            max_energy = max(max_energy, energy)
            if debug:
                print(f"Audio energy: {energy:.2f} (max: {max_energy:.2f})", end='\r')
    
    if debug:
        print(f"\nMax energy detected: {max_energy:.2f}")
    
    if max_energy < 100:
        logger.warning("Very low audio levels detected. Check microphone connection.")
        suggested_threshold = max(50, max_energy * 0.8)
    else:
        suggested_threshold = max_energy * 0.3
    
    logger.info(f"Suggested energy threshold: {suggested_threshold:.2f}")
    return suggested_threshold