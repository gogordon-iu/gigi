import asyncio
import subprocess
import numpy as np
import pyaudio
import json
import re
import atexit
import os
import time
import threading
import tempfile
import wave
from faster_whisper import WhisperModel
import requests
import sys
_current_file_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_file_dir)
_resources_dir = os.path.join(_project_root, 'Resources')
if _resources_dir not in sys.path:
    sys.path.insert(0, _resources_dir)
from nix.models.TTS import NixTTSInference
from nix.tokenizers.tokenizer_en import NixTokenizerEN
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
from scipy import signal  # For resampling

# Suppress ALSA warnings
os.environ['ALSA_PCM_CARD'] = '0'
os.environ['ALSA_PCM_DEVICE'] = '0'
warnings.filterwarnings("ignore", category=UserWarning)

class VoiceCommunicator:
    def __init__(self, 
                 nix_model_dir=None,
                 whisper_model="tiny",
                 whisper_device="cpu",
                 ollama_model="llama3.2:1b-instruct-q4_K_M",
                 ollama_url="http://localhost:11434",
                 default_microphone=2):
        
        if nix_model_dir is None:
            _current_file_dir = os.path.dirname(os.path.abspath(__file__))
            _project_root = os.path.dirname(_current_file_dir)
            nix_model_dir = os.path.join(_project_root, 'Resources', 'nix', 'models')
            
        print("🚀 Initializing Voice Communicator...")
        
        # Initialize ALL attributes first
        self.selected_input = None
        self.default_microphone = default_microphone
        self.device_info = {}
        self.input_devices = []
        self.output_devices = []
        self.should_stop = False
        self.audio = None
        self.nix = None
        self.whisper_model = None
        self.current_stream = None
        
        # Initialize audio settings FIRST
        self.sample_rate = 16000  # Device sample rate
        self.whisper_sample_rate = 16000  # Whisper always needs 16000 Hz
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        
        # Initialize PyAudio
        self.initialize_audio()
        
        # Find and select audio devices
        self.setup_audio_devices()
        
        # Initialize TTS
        print("Loading TTS...")
        try:
            self.nix = NixTTSInference(model_dir=nix_model_dir)
            print("✅ TTS ready")
        except Exception as e:
            print(f"❌ TTS failed: {e}")
            raise
        
        # Initialize Faster Whisper
        print("Loading Whisper...")
        try:
            self.whisper_model = WhisperModel(
                whisper_model, 
                device=whisper_device, 
                compute_type="int8"
            )
            print("✅ Whisper ready")
        except Exception as e:
            print(f"❌ Whisper failed: {e}")
            raise
        
        # Ollama settings
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        
        # Conversation memory
        self.conversation_history = []
        self.max_history = 5  # Keep last 10 exchanges (20 messages) to save memory
        
        # Register cleanup
        atexit.register(self.cleanup)
        
        print("🎉 Ready!")
    
    def initialize_audio(self):
        """Initialize PyAudio with proper error handling"""
        try:
            # Redirect stderr to suppress ALSA warnings
            stderr = os.dup(2)
            os.close(2)
            os.open(os.devnull, os.O_RDWR)
            try:
                self.audio = pyaudio.PyAudio()
                print("✅ PyAudio initialized")
            finally:
                os.dup2(stderr, 2)
                os.close(stderr)
        except Exception as e:
            print(f"❌ PyAudio failed: {e}")
            self.audio = None
            raise
    
    def setup_audio_devices(self):
        """Setup audio devices with USB microphone priority"""
        if self.audio is None:
            print("❌ No PyAudio instance")
            return
        
        print("\n🔍 Scanning audio devices...")
        
        try:
            device_count = self.audio.get_device_count()
            print(f"Found {device_count} audio devices")
            
            self.input_devices = []
            self.output_devices = []
            self.device_info = {}
            
            # Prioritize USB devices
            usb_devices = []
            other_devices = []
            
            for i in range(device_count):
                try:
                    info = self.audio.get_device_info_by_index(i)
                    self.device_info[i] = info
                    
                    device_name = info['name']
                    print(f"\nDevice {i}: {device_name}")
                    print(f"  Max Input Channels: {info['maxInputChannels']}")
                    print(f"  Default Sample Rate: {info['defaultSampleRate']}")
                    
                    if info['maxInputChannels'] > 0:
                        if 'usb' in device_name.lower() or 'uac' in device_name.lower():
                            usb_devices.append(i)
                            print(f"  ✅ USB INPUT DEVICE")
                        else:
                            other_devices.append(i)
                            print(f"  ✅ INPUT DEVICE")
                        
                except Exception as e:
                    print(f"  ❌ Error reading device {i}: {e}")
                    continue
            
            # Combine USB devices first, then others
            self.input_devices = usb_devices + other_devices
            
            print(f"\n📊 Summary: {len(self.input_devices)} input devices ({len(usb_devices)} USB)")
            
            if len(self.input_devices) == 0:
                print("❌ No input devices found!")
                self.selected_input = None
                return
            
            # Try to use the specified USB microphone first
            if self.default_microphone in self.input_devices:
                self.selected_input = self.default_microphone
                print(f"🎤 Using specified USB microphone: {self.default_microphone}")
            elif len(usb_devices) > 0:
                self.selected_input = usb_devices[0]
                print(f"🎤 Using first USB microphone: {self.selected_input}")
            else:
                self.selected_input = self.input_devices[0]
                print(f"🎤 Using first available microphone: {self.selected_input}")
            
            # Find working sample rate
            self.find_working_sample_rate()
            
        except Exception as e:
            print(f"❌ Device scanning failed: {e}")
            self.selected_input = None
    
    def find_working_sample_rate(self):
        """Find a working sample rate for the selected device"""
        if self.selected_input is None:
            return
        
        device_name = self.device_info.get(self.selected_input, {}).get('name', 'Unknown')
        print(f"\n🎛️ Finding working sample rate for: {device_name}")
        
        # Common sample rates to try (prefer 16000 for Whisper)
        sample_rates = [16000, 44100, 48000, 22050, 8000]
        
        for rate in sample_rates:
            print(f"Testing {rate} Hz...", end=" ")
            stream = None
            try:
                stream = self.audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=rate,
                    input=True,
                    input_device_index=self.selected_input,
                    frames_per_buffer=self.chunk_size,
                    start=False
                )
                
                # Try to start and read from stream
                stream.start_stream()
                
                # Try to read a few chunks
                frames = []
                for i in range(5):
                    try:
                        data = stream.read(self.chunk_size, exception_on_overflow=False)
                        frames.append(data)
                    except:
                        break
                
                if frames:
                    audio_data = b''.join(frames)
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    level = np.abs(audio_np).mean()
                    
                    print(f"✅ Success (level: {level:.1f})")
                    self.sample_rate = rate
                    
                    stream.stop_stream()
                    stream.close()
                    print(f"🎉 Using sample rate: {rate} Hz")
                    if rate != self.whisper_sample_rate:
                        print(f"⚠️ Will resample from {rate} Hz to {self.whisper_sample_rate} Hz for Whisper")
                    return
                else:
                    print("❌ No data")
                
                stream.stop_stream()
                stream.close()
                
            except Exception as e:
                print(f"❌ Failed: {e}")
                if stream:
                    try:
                        if stream.is_active():
                            stream.stop_stream()
                        stream.close()
                    except:
                        pass
                continue
        
        print("❌ No working sample rate found! Using default 16000 Hz")
        self.sample_rate = 16000
    
    def resample_audio(self, audio_np, original_rate, target_rate):
        """Resample audio to target sample rate"""
        if original_rate == target_rate:
            return audio_np
        
        print(f"🔄 Resampling from {original_rate} Hz to {target_rate} Hz...")
        
        # Calculate resampling ratio
        num_samples = int(len(audio_np) * target_rate / original_rate)
        
        # Use scipy's resample for high-quality resampling
        resampled = signal.resample(audio_np, num_samples)
        
        return resampled.astype(np.float32)
    
    def visualize_audio(self, audio_np, label="Audio"):
        """Visualize audio data for debugging"""
        if len(audio_np) == 0:
            print(f"📊 {label}: EMPTY")
            return
        
        level = np.abs(audio_np).mean()
        max_level = np.abs(audio_np).max()
        
        # Create simple bar visualization
        bar_length = 50
        bar = int((level / 1000) * bar_length)
        bar = min(bar, bar_length)
        
        print(f"📊 {label}:")
        print(f"   Mean: {level:.1f} | Max: {max_level:.1f}")
        print(f"   Level: [{'=' * bar}{' ' * (bar_length - bar)}]")
    
    def create_audio_stream(self):
        """Create a new audio stream with error handling"""
        if self.selected_input is None:
            return None
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stream = self.audio.open(
                    format=self.format,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.selected_input,
                    frames_per_buffer=self.chunk_size,
                    start=False
                )
                
                stream.start_stream()
                print(f"✅ Audio stream created (attempt {attempt + 1})")
                return stream
                
            except Exception as e:
                print(f"❌ Stream creation failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    print("🔄 Retrying...")
                    time.sleep(0.5)
                    # Try to reinitialize audio if device becomes unavailable
                    if "unavailable" in str(e).lower():
                        self.cleanup_audio()
                        self.initialize_audio()
                continue
        
        return None
    
    def cleanup_audio(self):
        """Clean up audio resources"""
        if hasattr(self, 'current_stream') and self.current_stream:
            try:
                if self.current_stream.is_active():
                    self.current_stream.stop_stream()
                self.current_stream.close()
                self.current_stream = None
            except:
                pass
        
        if self.audio:
            try:
                self.audio.terminate()
                self.audio = None
            except:
                pass
    
    def record_robust(self, duration=5):
        """Robust recording with device recovery"""
        if self.selected_input is None:
            print("❌ No microphone selected")
            return b""
        
        print(f"🎤 Recording {duration}s...")
        
        stream = None
        try:
            stream = self.create_audio_stream()
            if stream is None:
                print("❌ Could not create audio stream")
                return b""
            
            self.current_stream = stream
            
            # Clear buffer
            time.sleep(0.1)
            for _ in range(3):
                try:
                    stream.read(self.chunk_size, exception_on_overflow=False)
                except:
                    break
            
            frames = []
            num_chunks = int(self.sample_rate * duration / self.chunk_size)
            
            print("🔊 Listening...", end="", flush=True)
            
            for i in range(num_chunks):
                if self.should_stop:
                    break
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    frames.append(data)
                    if i % 20 == 0:
                        print(".", end="", flush=True)
                except Exception as e:
                    print(f"❌ Read error at chunk {i}: {e}")
                    # If we get a read error, try to recover
                    if "input overflowed" in str(e).lower():
                        continue
                    else:
                        break
            
            print()  # New line
            
            audio_data = b''.join(frames)
            
            if audio_data:
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                self.visualize_audio(audio_np, "Recorded")
                
                level = np.abs(audio_np).mean()
                print(f"📊 Recorded {len(audio_data)} bytes, level: {level:.1f}")
                
                if level < 10:
                    print("⚠️ WARNING: Very quiet recording - speak louder or check mic gain!")
                elif level > 5000:
                    print("⚠️ WARNING: Very loud recording - reduce gain to avoid clipping!")
                
                return audio_data
            else:
                print("❌ No audio data captured")
                return b""
            
        except Exception as e:
            print(f"❌ Recording failed: {e}")
            return b""
        finally:
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                    self.current_stream = None
                except:
                    pass
    
    def transcribe_whisper_robust(self, audio_data):
        """Robust transcription with multiple attempts and proper resampling"""
        if not audio_data or len(audio_data) < 4000:
            print("❌ Audio data too short")
            return ""
        
        try:
            # Convert to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0
            
            # Resample if necessary
            if self.sample_rate != self.whisper_sample_rate:
                audio_float = self.resample_audio(audio_float, self.sample_rate, self.whisper_sample_rate)
            
            self.visualize_audio(audio_float * 32768, "Preprocessed for Whisper")
            
            print("🎯 Transcribing...")
            
            # Approach 1: NO VAD - most reliable for short recordings
            print("🔄 Attempt 1: No VAD (most reliable)...")
            try:
                segments, info = self.whisper_model.transcribe(
                    audio_float,
                    language="en",
                    task="transcribe",
                    beam_size=5,
                    best_of=5,
                    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                    vad_filter=False,  # Disable VAD
                    no_speech_threshold=0.3,  # Lower threshold
                    compression_ratio_threshold=2.4,
                    condition_on_previous_text=False
                )
                
                texts = []
                for segment in segments:
                    text = segment.text.strip()
                    confidence = segment.avg_logprob
                    print(f"📝 Segment: '{text}' (confidence: {confidence:.2f}, no_speech_prob: {segment.no_speech_prob:.2f})")
                    
                    # Accept if text is meaningful and confidence isn't terrible
                    if text and len(text) > 1 and segment.no_speech_prob < 0.8:
                        texts.append(text)
                
                if texts:
                    result = ' '.join(texts).strip()
                    print(f"✅ Transcription: '{result}'")
                    return result
            except Exception as e:
                print(f"⚠️ Attempt 1 failed: {e}")
            
            # Approach 2: With gentle VAD settings
            print("🔄 Attempt 2: Gentle VAD...")
            try:
                segments, info = self.whisper_model.transcribe(
                    audio_float,
                    language="en",
                    task="transcribe",
                    beam_size=3,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=100,  # Much shorter
                        threshold=0.3,  # More sensitive
                        max_speech_duration_s=30
                    ),
                    no_speech_threshold=0.3
                )
                
                texts = []
                for segment in segments:
                    text = segment.text.strip()
                    if text and len(text) > 1:
                        texts.append(text)
                        print(f"📝 VAD: '{text}' (confidence: {segment.avg_logprob:.2f})")
                
                if texts:
                    result = ' '.join(texts).strip()
                    print(f"✅ VAD transcription: '{result}'")
                    return result
            except Exception as e:
                print(f"⚠️ Attempt 2 failed: {e}")
            
            # Approach 3: Ultra-sensitive, accept almost anything
            print("🔄 Attempt 3: Ultra-sensitive...")
            try:
                segments, info = self.whisper_model.transcribe(
                    audio_float,
                    language="en",
                    task="transcribe",
                    beam_size=1,
                    vad_filter=False,
                    no_speech_threshold=0.1,  # Very low
                    initial_prompt="This is a voice conversation."
                )
                
                texts = []
                for segment in segments:
                    text = segment.text.strip()
                    if text and len(text) > 0:  # Accept even single characters
                        texts.append(text)
                        print(f"📝 Ultra-sensitive: '{text}'")
                
                if texts:
                    result = ' '.join(texts).strip()
                    print(f"✅ Ultra-sensitive transcription: '{result}'")
                    return result
            except Exception as e:
                print(f"⚠️ Attempt 3 failed: {e}")
            
            # Approach 4: Save audio and try absolute minimum settings
            print("🔄 Attempt 4: Saving audio file and using minimal settings...")
            try:
                # Save audio to WAV file for debugging
                import wave
                debug_file = "/tmp/debug_recording.wav"
                with wave.open(debug_file, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.whisper_sample_rate)
                    wf.writeframes((audio_float * 32768).astype(np.int16).tobytes())
                print(f"💾 Saved to {debug_file} - you can play this with: aplay {debug_file}")
                
                # Try with absolute minimum settings
                segments, info = self.whisper_model.transcribe(
                    audio_float,
                    language="en"
                )
                
                texts = []
                all_segments = list(segments)
                print(f"🔍 Found {len(all_segments)} segments total")
                
                for segment in all_segments:
                    text = segment.text.strip()
                    print(f"📝 Raw segment: '{text}' (no_speech_prob: {segment.no_speech_prob:.2f})")
                    if text:
                        texts.append(text)
                
                if texts:
                    result = ' '.join(texts).strip()
                    print(f"✅ Minimal settings transcription: '{result}'")
                    return result
                else:
                    print(f"⚠️ Model detected {len(all_segments)} segments but all were filtered/empty")
            except Exception as e:
                print(f"⚠️ Attempt 4 failed: {e}")
                import traceback
                traceback.print_exc()
            
            print("❌ No speech detected with any method")
            print("💡 Tips:")
            print("   - Speak louder and closer to the microphone")
            print("   - Check if mic is muted or gain is too low")
            print("   - Test with: 'arecord -d 3 test.wav' then 'aplay test.wav'")
            return ""
                
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def speak_simple(self, text):
        """Simple TTS"""
        if not text.strip():
            return
        
        try:
            c, c_length, _ = self.nix.tokenizer([text])
            xw = self.nix.vocalize(c, c_length)[0, 0].astype(np.float32)
            
            temp_file = "/tmp/tts_temp.raw"
            pcm_data = (xw * 32767).astype(np.int16)
            
            with open(temp_file, 'wb') as f:
                f.write(pcm_data.tobytes())
            
            subprocess.run([
                'play', '-t', 'raw', '-r', '22050', '-e', 'signed-integer', 
                '-b', '16', '-c', '1', temp_file, 'vol', '1.0'
            ], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            
            try:
                os.remove(temp_file)
            except:
                pass
                
        except Exception as e:
            print(f"❌ Speaking failed: {e}")

    def get_response_with_tts_sync(self, text):
        """Get LLM response with conversation memory"""
        if not text:
            return "I didn't understand that."
        
        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": text
            })
            
            # Trim history to keep memory usage low
            # Keep system message + last N exchanges
            if len(self.conversation_history) > (self.max_history * 2):
                # Keep first message if it's a system message, otherwise start fresh
                if self.conversation_history[0].get("role") == "system":
                    self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-(self.max_history * 2):]
                else:
                    self.conversation_history = self.conversation_history[-(self.max_history * 2):]
            
            # Use /api/chat endpoint for conversation support
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": self.conversation_history,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 100
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                assistant_message = response.json()["message"]["content"].strip()
                
                # Add assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                print(f"🤖 AI: {assistant_message}")
                print(f"💾 History: {len(self.conversation_history)} messages")
                self.speak_simple(assistant_message)
                return assistant_message
            else:
                error_msg = "Sorry, having trouble responding."
                self.speak_simple(error_msg)
                return error_msg
                
        except Exception as e:
            print(f"❌ LLM error: {e}")
            error_msg = "Connection issue."
            self.speak_simple(error_msg)
            return error_msg
    
    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        print("🔄 Conversation history cleared")

    def run_conversation(self):
        """Main conversation with robust audio handling"""
        print("\n" + "="*50)
        print("🎮 VOICE CHAT - WITH MEMORY")
        print("="*50)
        
        if self.selected_input is None:
            print("❌ No microphone available")
            return
        
        device_name = self.device_info.get(self.selected_input, {}).get('name', 'Unknown')
        print(f"🎤 Using: {device_name}")
        print(f"📊 Recording at: {self.sample_rate} Hz")
        print(f"📊 Whisper expects: {self.whisper_sample_rate} Hz")
        print("\nCommands:")
        print("  - Press Enter: Start recording")
        print("  - Type 'q': Quit")
        print("  - Type 'reset': Clear conversation memory")
        print("  - Type 'system <message>': Set system prompt")
        
        # Optional: Set a system message for better responses
        system_msg = input("\n[Optional] Set system personality (or press Enter to skip): ").strip()
        if system_msg:
            self.conversation_history.append({
                "role": "system",
                "content": system_msg
            })
            print(f"✅ System prompt set: {system_msg}")
        else:
            # Default system message for brief responses
            self.conversation_history.append({
                "role": "system",
                "content": "You are a helpful voice assistant. Keep responses brief and conversational."
            })
            print("✅ Using default system prompt")
        
        self.speak_simple("Ready for conversation!")
        
        conversation_count = 0
        
        while not self.should_stop:
            try:
                user_input = input(f"\n[Chat {conversation_count + 1}] Press Enter to speak (or command): ").strip()
                
                if user_input.lower() in ['q', 'quit', 'exit']:
                    break
                
                # Handle reset command
                if user_input.lower() == 'reset':
                    self.reset_conversation()
                    # Re-add system message
                    self.conversation_history.append({
                        "role": "system",
                        "content": "You are a helpful voice assistant. Keep responses brief and conversational."
                    })
                    self.speak_simple("Memory cleared!")
                    continue
                
                # Handle system message command
                if user_input.lower().startswith('system '):
                    new_system = user_input[7:].strip()
                    self.reset_conversation()
                    self.conversation_history.append({
                        "role": "system",
                        "content": new_system
                    })
                    print(f"✅ New system prompt: {new_system}")
                    self.speak_simple("System prompt updated!")
                    continue
                
                # Record with robust method
                audio_data = self.record_robust(duration=5)
                
                if not audio_data:
                    print("❌ Recording failed - trying to recover...")
                    # Try to recover by reinitializing audio
                    self.cleanup_audio()
                    time.sleep(0.5)
                    self.initialize_audio()
                    time.sleep(1)
                    continue
                
                # Transcribe
                text = self.transcribe_whisper_robust(audio_data)
                
                if not text:
                    print("❌ No speech detected")
                    self.speak_simple("I didn't hear anything. Please try again.")
                    continue
                
                print(f"👤 You: {text}")
                
                # Stop command
                if any(word in text.lower() for word in ['goodbye', 'bye', 'quit', 'exit', 'stop']):
                    self.speak_simple("Goodbye!")
                    break
                
                # Get response
                response = self.get_response_with_tts_sync(text)
                conversation_count += 1
                
                # Small delay to let audio settle
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                # Recover from error
                self.cleanup_audio()
                time.sleep(0.5)
                self.initialize_audio()
                continue

    def cleanup(self):
        """Cleanup"""
        self.should_stop = True
        self.cleanup_audio()

def main():
    """Main function"""
    try:
        print("🚀 Voice Communicator - WITH CONVERSATION MEMORY")
        print("="*50)
        
        # Check if scipy is available
        try:
            import scipy
            print("✅ scipy available for resampling")
        except ImportError:
            print("⚠️ WARNING: scipy not found!")
            print("   Install with: pip install scipy")
            print("   Resampling will not work without it!")
            return
        
        comm = VoiceCommunicator()
        comm.run_conversation()
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'comm' in locals():
            comm.cleanup()

if __name__ == "__main__":
    main()