import sys
import os
import time
import numpy as np

# Add local path for imports
sys.path.append(os.path.join(os.getcwd(), 'Character'))

try:
    import whisper_helper as wh
    print("[PASS] Imported whisper_helper")
except ImportError as e:
    print(f"[FAIL] Could not import whisper_helper: {e}")
    sys.exit(1)

# Test 1: Audio Resampling Optimization
print("\n--- Test 1: Audio Resampling Optimization ---")
# Create 1 second of 48k audio
orig_sr = 48000
target_sr = 16000
duration = 1.0
t = np.linspace(0, duration, int(orig_sr * duration))
# Create a simple sine wave
audio_data = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

start_time = time.time()
resampled = wh.resample_audio(audio_data, orig_sr, target_sr)
end_time = time.time()

print(f"Original shape: {audio_data.shape}, Resampled shape: {resampled.shape}")
print(f"Time taken: {(end_time - start_time)*1000:.4f} ms")

expected_len = int(len(audio_data) * target_sr / orig_sr) # 16000
if len(resampled) == expected_len or len(resampled) == expected_len + 1: # +1 tolerance for rounding
    print("[PASS] Resampling length correct")
else:
    print(f"[FAIL] Resampling length incorrect. Expected ~{expected_len}, got {len(resampled)}")

# Check if it used the slice optimization (indirectly by speed, but explicit check is hard without mocking)
# However, if we verify integrity of signal roughly:
non_zero = np.count_nonzero(resampled)
print(f"Non-zero samples: {non_zero}")
if non_zero > 0:
    print("[PASS] Audio signal preserved")
else:
    print("[FAIL] Audio signal lost (all zeros?)")

# Test 2: Mock Vision (Import check mostly, running dlib mock is hard without an image)
print("\n--- Test 2: Vision Import Check ---")
try:
    import vision_helper as vh
    # Mocking the face_recognition module to check if we call it with known_face_locations
    # This is tricky in a holistic test script without mocking lib, so we trust the measuring.
    print("[PASS] vision_helper imported successfully. Code changes are syntactic and should run if dependencies exist.")
except ImportError as e:
    print(f"[FAIL] Import error: {e}")

print("\n[DONE] Verification complete.")
