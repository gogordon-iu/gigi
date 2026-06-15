#!/usr/bin/env python3
import os
import sys
import time
import threading

# Add Character folder to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../Character'))

try:
    import sounddevice as sd
    print("sounddevice library loaded successfully.")
except ImportError as e:
    print(f"Error importing sounddevice: {e}")
    sys.exit(1)

try:
    from hearing import Hearing, HEARING_OPTION
    from characterDefinitions import USE_NPU_TRANSCRIPTION, IS_ROBOT
except ImportError as e:
    print(f"Error importing Gigi character components: {e}")
    sys.exit(1)

def test_transcription():
    print("\n" + "="*50)
    print("        GIGI TRANSCRIPTION TEST SCRIPT        ")
    print("="*50)
    print(f"System Platform: {sys.platform}")
    print(f"IS_ROBOT: {IS_ROBOT}")
    print(f"HEARING_OPTION: {HEARING_OPTION}")
    print(f"USE_NPU_TRANSCRIPTION: {USE_NPU_TRANSCRIPTION}")
    
    print("\n--- Audio Devices Scan ---")
    try:
        devices = sd.query_devices()
        print("Available Audio Devices:")
        for idx, dev in enumerate(devices):
            input_ch = dev.get('max_input_channels', 0)
            output_ch = dev.get('max_output_channels', 0)
            print(f"  [{idx}] {dev['name']} (Inputs: {input_ch}, Outputs: {output_ch})")
        
        default_input = sd.default.device[0]
        print(f"Default Input Device: {default_input} ({devices[default_input]['name'] if default_input is not None and default_input >= 0 else 'None'})")
    except Exception as e:
        print(f"Error scanning audio devices: {e}")

    print("\n--- Initializing Gigi Hearing Class ---")
    try:
        # Initialize Hearing
        hearing = Hearing(verbose=True)
        print(f"Hearing class initialized successfully!")
        print(f"Resolved self.mic_index: {hearing.mic_index}")
        print(f"Using RKNN: {getattr(hearing, 'use_rknn', False)}")
    except Exception as e:
        print(f"Critical error initializing Hearing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n--- Testing InputStream Initialization ---")
    # Let's see if we can open the InputStream
    stream = None
    try:
        def dummy_callback(indata, frames, time, status):
            pass
        
        # We test opening with resolved mic_index
        print(f"Trying to open sd.InputStream on device {hearing.mic_index}...")
        stream = sd.InputStream(
            samplerate=48000,
            channels=1,
            device=hearing.mic_index,
            callback=dummy_callback,
            blocksize=8192,
            dtype='int16'
        )
        with stream:
            print("InputStream opened successfully!")
    except Exception as e:
        print(f"Failed to open InputStream with mic_index={hearing.mic_index}: {e}")
        print("Testing with device=None (default device)...")
        try:
            stream = sd.InputStream(
                samplerate=48000,
                channels=1,
                device=None,
                callback=dummy_callback,
                blocksize=8192,
                dtype='int16'
            )
            with stream:
                print("InputStream opened successfully on default device!")
        except Exception as e2:
            print(f"Failed to open InputStream on default device: {e2}")
            import traceback
            traceback.print_exc()

    # Now let's run the real listen_fluid loop
    print("\n" + "="*50)
    print("  PROMPT: Speak clearly into the microphone now!  ")
    print("="*50)
    print("Starting fluid listening for 8 seconds. Talk now...")
    
    stop_event = threading.Event()
    # Auto stop after 8 seconds
    def auto_stop():
        time.sleep(8.0)
        print("\n--- Time limit reached (8 seconds). Stopping ---")
        stop_event.set()
        
    threading.Thread(target=auto_stop, daemon=True).start()
    
    # Mock face for status logging
    class MockFace:
        def __init__(self):
            self.feedback_state = None
            self.reading_status = None
        def set_reading_status(self, status):
            self.reading_status = status
            print(f"  [UI Status Change] -> {status.upper()}")
            
    hearing.face = MockFace()
    hearing.clear_audio_buffer()
    
    try:
        # This calls listen_fluid which performs real-time VAD and STT
        hearing.listen_fluid(stop_event=stop_event, n_transcripts=1)
    except Exception as e:
        print(f"Error during listen_fluid: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n" + "="*50)
    print("Test finished!")
    print(f"All Transcribed Texts: {hearing.texts}")
    print("="*50)

if __name__ == "__main__":
    test_transcription()
