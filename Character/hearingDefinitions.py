# Parameters
INPUT_SAMPLE_RATE = 48000  # Whisper works best with 16kHz audio
CHUNK_DURATION = 5   # Duration of audio chunks in seconds
SILENCE_THRESHOLD = 0.01  # Threshold for detecting silence
SILENCE_DURATION = 2      # Stop after this many seconds of silence