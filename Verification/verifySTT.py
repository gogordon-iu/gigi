#!/usr/bin/env python3
"""
Simple Real-time Speech-to-Text using Faster Whisper
Optimized for Orange Pi with debugging features
"""

import pyaudio
import wave
import numpy as np
from faster_whisper import WhisperModel
import threading
import queue
import time
import os
import webrtcvad

class RealTimeSTT:
    def __init__(self, model_size="base", device="cpu"):
        """
        Initialize the real-time STT system
        
        Args:
            model_size: "tiny", "base", "small", "medium", "large-v2" 
                       (smaller models work better on Orange Pi)
            device: "cpu" or "cuda" (use "cpu" for Orange Pi)
        """
        print(f"Initializing Faster Whisper model: {model_size}")
        
        # Initialize Whisper model
        self.model = WhisperModel(model_size, device=device, compute_type="int8")
        print("Model loaded successfully!")
        
        # Audio configuration
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000  # Whisper works best with 16kHz
        self.RECORD_SECONDS = 5  # Increased to 5 seconds for better word capture
        self.OVERLAP_SECONDS = 1  # 1 second overlap between chunks to avoid cutting words
        
        # VAD configuration
        self.vad = webrtcvad.Vad(1)  # Reduced aggressiveness to catch quieter speech
        self.vad_frame_duration = 30  # ms (10, 20, or 30)
        self.vad_frame_size = int(self.RATE * self.vad_frame_duration / 1000)
        self.speech_threshold = 0.15  # Lowered threshold to be more sensitive
        
        # Buffering for overlap
        self.overlap_buffer = []
        
        # Audio buffer and queue
        self.audio_queue = queue.Queue()
        self.audio_buffer = []
        
        # Control flags
        self.is_recording = False
        self.is_processing = False
        
        print(f"Audio settings: {self.RATE}Hz, {self.CHANNELS} channel(s)")
        print(f"Processing: {self.RECORD_SECONDS}s chunks with {self.OVERLAP_SECONDS}s overlap")
        print(f"VAD settings: Aggressiveness={1}, Frame={self.vad_frame_duration}ms, Threshold={self.speech_threshold}")
    
    def contains_speech(self, audio_data):
        """
        Check if audio chunk contains speech using WebRTC VAD
        
        Args:
            audio_data: numpy array of audio samples (int16)
            
        Returns:
            bool: True if speech is detected, False otherwise
        """
        # Convert to bytes for VAD
        audio_bytes = audio_data.astype(np.int16).tobytes()
        
        # Split audio into VAD frames
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(audio_bytes), self.vad_frame_size * 2):  # *2 for 16-bit samples
            frame = audio_bytes[i:i + self.vad_frame_size * 2]
            
            # Skip incomplete frames
            if len(frame) < self.vad_frame_size * 2:
                continue
                
            # Check if frame contains speech
            try:
                if self.vad.is_speech(frame, self.RATE):
                    speech_frames += 1
                total_frames += 1
            except:
                continue
        
        # Calculate speech ratio
        if total_frames == 0:
            return False
            
        speech_ratio = speech_frames / total_frames
        return speech_ratio >= self.speech_threshold
    
    def audio_callback(self, in_data, frame_count, time_info, status):
        """Callback function for audio input"""
        if status:
            pass  # Ignore audio status messages
        
        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        self.audio_buffer.extend(audio_data)
        
        # Process when we have enough data
        if len(self.audio_buffer) >= self.RATE * self.RECORD_SECONDS:
            # Get overlap from previous chunk
            overlap_size = int(self.RATE * self.OVERLAP_SECONDS)
            
            # Create chunk with overlap
            if len(self.overlap_buffer) >= overlap_size:
                # Combine overlap + new audio
                audio_chunk = np.array(self.overlap_buffer[-overlap_size:] + self.audio_buffer[:self.RATE * self.RECORD_SECONDS], dtype=np.int16)
            else:
                # Not enough overlap yet, use current buffer
                audio_chunk = np.array(self.audio_buffer[:self.RATE * self.RECORD_SECONDS], dtype=np.int16)
            
            # Store overlap for next chunk
            self.overlap_buffer = list(self.audio_buffer[:self.RATE * self.RECORD_SECONDS])
            
            # Remove processed data from buffer
            self.audio_buffer = self.audio_buffer[self.RATE * (self.RECORD_SECONDS - self.OVERLAP_SECONDS):]
            
            # Check if chunk contains speech using VAD
            if self.contains_speech(audio_chunk):
                # Convert to float32 for Whisper processing
                audio_float = audio_chunk.astype(np.float32) / 32768.0
                
                # Add to processing queue
                if not self.audio_queue.full():
                    self.audio_queue.put(audio_float)
            # If no speech detected, chunk is silently discarded
        
        return (in_data, pyaudio.paContinue)
    
    def process_audio(self):
        """Process audio from the queue"""
        continuous_text = ""
        last_segment_words = []  # Store last few words to avoid duplicates
        
        while self.is_processing:
            try:
                # Get audio chunk from queue (timeout to avoid blocking)
                audio_chunk = self.audio_queue.get(timeout=1.0)
                
                # Transcribe using Faster Whisper with better parameters
                segments, info = self.model.transcribe(
                    audio_chunk, 
                    beam_size=2,  # Increased beam size for better accuracy
                    best_of=2,    # Consider multiple candidates
                    language="en",  # Set to your language or None for auto-detect
                    condition_on_previous_text=False,  # Disable to reduce overlap repetition
                    word_timestamps=True,  # Enable word-level timestamps
                    vad_filter=False,  # We already did VAD filtering
                    no_speech_threshold=0.4,  # Lower threshold to catch more speech
                    compression_ratio_threshold=2.4  # More lenient compression check
                )
                
                # Extract text from segments and handle duplicates
                new_text = ""
                current_words = []
                
                for segment in segments:
                    words = segment.text.strip().split()
                    current_words.extend(words)
                
                if current_words:
                    # Remove duplicate words from overlap
                    if last_segment_words:
                        # Find overlap between last segment and current segment
                        overlap_length = 0
                        for i in range(1, min(len(last_segment_words), len(current_words)) + 1):
                            if last_segment_words[-i:] == current_words[:i]:
                                overlap_length = i
                        
                        # Remove overlapping words from current segment
                        unique_words = current_words[overlap_length:]
                    else:
                        unique_words = current_words
                    
                    # Update last segment words (keep last 10 words for next comparison)
                    last_segment_words = current_words[-10:] if len(current_words) > 10 else current_words
                    
                    # Add unique words to continuous text
                    if unique_words:
                        new_text = " ".join(unique_words)
                        continuous_text += new_text + " "
                        
                        # Clear screen and show continuous text
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print("=== Continuous Transcription ===")
                        print(continuous_text)
                        print("\n[Press Ctrl+C to stop]")
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error: {e}")
                continue
    
    def start_recording(self):
        """Start real-time recording and transcription"""
        try:
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Check available audio devices (only show if debugging)
            # print("\nAvailable audio devices:")
            # for i in range(self.audio.get_device_count()):
            #     info = self.audio.get_device_info_by_index(i)
            #     print(f"  {i}: {info['name']} (inputs: {info['maxInputChannels']})")
            
            # Open audio stream
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=self.audio_callback
            )
            
            print(f"\nStarting real-time transcription...")
            print("Speak into your microphone...")
            time.sleep(2)  # Give user time to read message
            
            # Clear screen for clean transcription display
            os.system('clear' if os.name == 'posix' else 'cls')
            
            # Start processing thread
            self.is_recording = True
            self.is_processing = True
            
            processing_thread = threading.Thread(target=self.process_audio)
            processing_thread.daemon = True
            processing_thread.start()
            
            # Start audio stream
            self.stream.start_stream()
            
            # Keep the main thread alive
            while self.is_recording:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nStopping transcription...")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.stop_recording()
    
    def stop_recording(self):
        """Stop recording and clean up"""
        self.is_recording = False
        self.is_processing = False
        
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        
        if hasattr(self, 'audio'):
            self.audio.terminate()
        
        print("Recording stopped.")

def main():
    """Main function with debug information"""
    print("=== Real-time Speech-to-Text with Faster Whisper ===")
    print(f"Python version: {os.sys.version}")
    
    # Check if running on Orange Pi (ARM architecture)
    import platform
    print(f"Platform: {platform.machine()}")
    
    try:
        # Initialize STT system
        # Use "tiny" model as requested but with better parameters
        stt = RealTimeSTT(model_size="tiny", device="cpu")
        
        # Start real-time transcription
        stt.start_recording()
        
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("\nTo install required packages:")
        print("pip install faster-whisper pyaudio numpy webrtcvad")
        print("\nFor Orange Pi, you might also need:")
        print("sudo apt-get install portaudio19-dev python3-dev")
        
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()