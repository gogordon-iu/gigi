import json
from vosk import Model, KaldiRecognizer
import pyaudio

# Load the Vosk model
model = Model("../Resources/vosk-model-small-en-us-0.15")

# Create a recognizer with a limited vocabulary
rec = KaldiRecognizer(model, 48000, '["yes", "no", "[unk]"]')

# Set up microphone input
p = pyaudio.PyAudio()

audio = pyaudio.PyAudio()
usb_device_index = None

# List and find USB microphone
for i in range(audio.get_device_count()):
    device_info = audio.get_device_info_by_index(i)
    device_name = device_info['name']
    if "USB" in device_name.upper():  # Modify "USB" to match your device name if necessary
        usb_device_index = i
        print(f"Selected USB Microphone: {device_name} (Device Index {usb_device_index})")
        
    
stream = p.open(input_device_index=usb_device_index, format=pyaudio.paInt16, channels=1, rate=48000, input=True, frames_per_buffer=12000)
stream.start_stream()

print("Say 'yes' or 'no':")

while True:
    data = stream.read(12000, exception_on_overflow=False)
    if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        print(result["text"])
        print("Detected:", result.get("text", ""))
