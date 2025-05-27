import uuid

def generate_random_filename(extension="txt"):
    random_filename = f"{uuid.uuid4().hex}.{extension}"
    return random_filename

AUDIO_DELAY = 1.0   # have a one second delay after each sound
OUTPUT_SAMPLE_RATE = 48000

recorded_speech_path = "../Assets/recorded_speech/"
recorded_speech_filename = recorded_speech_path + "recorded.json"

audio_path = "../Assets/audio/"