import os
import sys
import time
import numpy as np
from PIL import Image
from unittest.mock import MagicMock

# 1. Simulate OrangePi 5 Pro environment by limiting CPU affinity to a single core
import psutil
try:
    p = psutil.Process()
    # Limit to Core 0
    p.cpu_affinity([0])
    print("[OPi Simulator] CPU affinity successfully restricted to Core 0.")
except Exception as e:
    print(f"[OPi Simulator] Warning: Could not set CPU affinity ({e}). Running on default cores.")

# Mock hardware dependencies to test robot code path on Windows
sys.modules['gpiod'] = MagicMock()
sys.modules['smbus2'] = MagicMock()


# 2. Benchmarks for Motor I2C controller
def benchmark_motors():
    print("\n--- Motor I2C Control Benchmark ---")
    
    # Simulate old way: open/close on every write
    start_old = time.time()
    mock_bus_class = MagicMock()
    for _ in range(50):  # 50 updates (e.g. 1 second of movement)
        # Old set_pwm code:
        for channel in range(4):
            # open bus, write 4 registers, close bus
            with mock_bus_class(5) as bus:
                bus.write_byte_data(0x40, 0x06 + 4*channel, 0)
                bus.write_byte_data(0x40, 0x07 + 4*channel, 0)
                bus.write_byte_data(0x40, 0x08 + 4*channel, 0)
                bus.write_byte_data(0x40, 0x09 + 4*channel, 0)
    old_duration = time.time() - start_old
    print(f"Old Way (Open/Close SMBus per write): {old_duration:.4f} seconds")
    
    # Simulate new way: single open bus, reuse
    start_new = time.time()
    bus = mock_bus_class(5)
    for _ in range(50):
        for channel in range(4):
            bus.write_byte_data(0x40, 0x06 + 4*channel, 0)
            bus.write_byte_data(0x40, 0x07 + 4*channel, 0)
            bus.write_byte_data(0x40, 0x08 + 4*channel, 0)
            bus.write_byte_data(0x40, 0x09 + 4*channel, 0)
    bus.close()
    new_duration = time.time() - start_new
    print(f"New Way (Reused SMBus connection): {new_duration:.4f} seconds")
    print(f"Speedup: {old_duration / max(1e-6, new_duration):.2f}x")


# 3. Benchmarks for Face Stacking & Formatting
def benchmark_face_rendering():
    print("\n--- Face Rendering Benchmark ---")
    # Generate mock PIL images (Eyes, Nose, Mouth slices)
    width, height = 640, 480
    eyes_h, nose_h, mouth_h = int(height * 0.41), int(height * 0.24), int(height * 0.35)
    
    eyes_pil = Image.new('RGB', (width, eyes_h), color='blue')
    nose_pil = Image.new('RGB', (width, nose_h), color='green')
    mouth_pil = Image.new('RGB', (width, mouth_h), color='red')
    
    global_parts = ["Eyes", "Nose", "Mouth"]
    images = {"Eyes": eyes_pil, "Nose": nose_pil, "Mouth": mouth_pil}
    
    # Benchmarking old PIL-based stack + conversion
    start_old = time.time()
    for _ in range(100):
        # 1. Resize if needed
        max_width = max(img.width for img in images.values())
        for part in global_parts:
            images[part] = images[part].resize((max_width, images[part].height))
        # 2. Stack images
        total_height = sum(img.height for img in images.values())
        stacked_image = Image.new('RGB', (max_width, total_height), color='white')
        y_offset = 0
        for part in global_parts:
            stacked_image.paste(images[part], (0, y_offset))
            y_offset += images[part].height
        # 3. Convert to cv2 numpy array
        cv_image = np.array(stacked_image)
        cv_image = cv_image[:, :, ::-1].copy()  # RGB to BGR
    old_duration = time.time() - start_old
    print(f"Old Way (PIL Stack & Resize & Convert on frame): {old_duration:.4f} seconds")
    
    # Benchmarking new NumPy vertical concatenation
    # Assume images are pre-converted to NumPy BGR arrays during startup
    images_np = {
        "Eyes": np.array(eyes_pil)[:, :, ::-1].copy(),
        "Nose": np.array(nose_pil)[:, :, ::-1].copy(),
        "Mouth": np.array(mouth_pil)[:, :, ::-1].copy()
    }
    
    start_new = time.time()
    for _ in range(100):
        cv_image = np.concatenate([images_np[part] for part in global_parts], axis=0)
    new_duration = time.time() - start_new
    print(f"New Way (Pre-converted NumPy Concatenation): {new_duration:.4f} seconds")
    print(f"Speedup: {old_duration / max(1e-6, new_duration):.2f}x")


# 4. Benchmarks for Audio Resampling and Envelope
def benchmark_audio_processing():
    print("\n--- Audio Resampling & Viseme Envelope Benchmark ---")
    
    # Generate 5 seconds of mock float32 audio at 22050Hz (Nix TTS rate)
    sr_orig = 22050
    duration = 5.0
    t = np.linspace(0, duration, int(sr_orig * duration), endpoint=False)
    audio = np.sin(2 * np.pi * 440 * t)  # 440Hz sine wave
    
    # Try importing librosa to run the baseline comparison
    try:
        import librosa
        has_librosa = True
    except ImportError:
        has_librosa = False
        print("librosa not installed; skipping baseline librosa benchmark.")
        
    if has_librosa:
        # Librosa Resampling
        start_lib_res = time.time()
        res_lib = librosa.resample(audio, orig_sr=sr_orig, target_sr=48000)
        lib_res_dur = time.time() - start_lib_res
        print(f"Librosa Resampling (22050 -> 48000 Hz): {lib_res_dur:.4f} seconds")
        
        # Librosa Envelope
        start_lib_env = time.time()
        env_lib = librosa.onset.onset_strength(y=audio, sr=sr_orig, hop_length=int(sr_orig * 0.1))
        lib_env_dur = time.time() - start_lib_env
        print(f"Librosa Onset Strength Envelope: {lib_env_dur:.4f} seconds")
    
    # NumPy Resampling
    def resample_linear(y, orig_sr, target_sr):
        if orig_sr == target_sr:
            return y
        dur = len(y) / orig_sr
        num_samples = int(dur * target_sr)
        old_x = np.linspace(0, dur, len(y))
        new_x = np.linspace(0, dur, num_samples)
        return np.interp(new_x, old_x, y)
        
    start_np_res = time.time()
    res_np = resample_linear(audio, sr_orig, 48000)
    np_res_dur = time.time() - start_np_res
    print(f"NumPy Linear Resampling (22050 -> 48000 Hz): {np_res_dur:.4f} seconds")
    
    # NumPy RMS Envelope
    def compute_rms_envelope(y, sr, sample_rate_hop=0.1):
        hop_length = int(sr * sample_rate_hop)
        if hop_length <= 0:
            return np.array([0.0])
        num_frames = int(np.ceil(len(y) / hop_length))
        envelope = np.zeros(num_frames)
        for i in range(num_frames):
            start = i * hop_length
            end = min(start + hop_length, len(y))
            frame = y[start:end]
            if len(frame) > 0:
                envelope[i] = np.sqrt(np.mean(frame**2))
        
        # Apply stretch factor
        stretch_factor = 1.5
        if stretch_factor != 1.0 and len(envelope) > 1:
            old_indices = np.arange(len(envelope))
            new_length  = int(len(envelope) * stretch_factor)
            new_indices = np.linspace(0, len(envelope) - 1, new_length)
            envelope    = np.interp(new_indices, old_indices, envelope)
            
        max_val = np.max(envelope)
        if max_val > 0:
            envelope = envelope / max_val
        envelope = np.minimum(envelope * 4, 1.0)
        return envelope
        
    start_np_env = time.time()
    env_np = compute_rms_envelope(audio, sr_orig)
    np_env_dur = time.time() - start_np_env
    print(f"NumPy RMS Envelope: {np_env_dur:.4f} seconds")
    
    if has_librosa:
        print(f"Resampling Speedup: {lib_res_dur / max(1e-6, np_res_dur):.2f}x")
        print(f"Envelope Speedup: {lib_env_dur / max(1e-6, np_env_dur):.2f}x")


if __name__ == '__main__':
    print("=== ORANGE PI 5 PRO SIMULATED PERFORMANCE SUITE ===")
    benchmark_motors()
    benchmark_face_rendering()
    benchmark_audio_processing()
    print("====================================================")
