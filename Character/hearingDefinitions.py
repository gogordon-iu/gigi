# Audio input parameters
INPUT_SAMPLE_RATE = 48000   # Native mic sample rate
TARGET_SAMPLE_RATE = 16000  # Whisper requires 16kHz

# Chunking and silence detection
CHUNK_DURATION = 5          # Duration of audio chunks in seconds
SILENCE_THRESHOLD = 0.02    # Amplitude threshold for silence detection
SILENCE_DURATION = 3.5        # Stop recording after this many seconds of silence

# Whisper transcription parameters
NO_SPEECH_THRESHOLD = 0.7   # Higher = stricter silence rejection (reduces hallucinations)
VAD_FILTER = True           # Enable Whisper's internal VAD as second layer filter
REPETITION_PENALTY = 1.3    # Penalize looping / repeating output
BEAM_SIZE = 2               # Beam search width (higher = more thorough)
BEST_OF = 2                 # Number of candidates to consider per transcription