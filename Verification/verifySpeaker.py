import sounddevice as sd
import numpy as np

def list_audio_devices():
    """
    List all available audio output devices.
    """
    devices = sd.query_devices()
    output_devices = [
        device for device in devices if device['max_output_channels'] > 0
    ]
    return output_devices

def get_usb_speaker():
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if d['max_output_channels'] > 0 and "USB" in d["name"]:
            return i
    raise RuntimeError("No USB speaker found!")


def play_beep(device_id):
    """
    Play a simple beep sound on the specified audio device.
    """
    duration = 1.0  # seconds
    frequency = 440.0  # Hz (A4 tone)
    sample_rate = 48000  # Hz
    
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    beep = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    sd.play(beep, samplerate=sample_rate, device=device_id)
    sd.wait()  # Wait until the sound is done playing

if __name__ == "__main__":
    print("Scanning for audio output devices...")
    devices = list_audio_devices()
    
    if not devices:
        print("No audio output devices found.")
    else:
        print("Available audio output devices:")
        for idx, device in enumerate(devices):
            print(f"{idx}: {device['name']}")
        
        # Use the first available output device
        first_device = get_usb_speaker()
        print(f"Using the first device: {first_device}")
        
        try:
            play_beep(first_device)
            print("Beep played successfully!")
        except Exception as e:
            print(f"Error playing beep: {e}")