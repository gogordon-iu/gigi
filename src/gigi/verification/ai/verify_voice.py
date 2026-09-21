#!/usr/bin/env python3
"""
Simple script to test speaker recognition using resemblyzer embeddings
"""

import pickle
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from pathlib import Path
import sounddevice as sd
import soundfile as sf
from scipy.io.wavfile import write
import tempfile

def load_speaker_db(db_path):
    """Load the speaker database from pickle file"""
    with open(db_path, 'rb') as f:
        speaker_db = pickle.load(f)
    return speaker_db

def record_audio(duration=3, sample_rate=16000):
    """Record audio from microphone"""
    print(f"\n🎤 Recording for {duration} seconds... Speak now!")
    audio = sd.rec(int(duration * sample_rate), 
                   samplerate=sample_rate, 
                   channels=1, 
                   dtype='float32')
    sd.wait()
    print("✓ Recording finished!")
    return audio.flatten(), sample_rate

def compute_similarity(embedding1, embedding2):
    """Compute cosine similarity between two embeddings"""
    return np.dot(embedding1, embedding2) / (
        np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
    )

def test_speaker(audio_path=None, speaker_db_path='../Resources/speaker_db.pkl', threshold=0.75):
    """
    Test if a speaker matches the database
    
    Args:
        audio_path: Path to audio file (if None, will record from mic)
        speaker_db_path: Path to speaker database pickle file
        threshold: Similarity threshold for matching (0-1)
    """
    # Load speaker database
    print("Loading speaker database...")
    speaker_db = load_speaker_db(speaker_db_path)
    
    print(f"Found {len(speaker_db)} speaker(s) in database:")
    for speaker_name in speaker_db.keys():
        print(f"  - {speaker_name}")
    
    # Initialize voice encoder
    print("\nInitializing voice encoder...")
    encoder = VoiceEncoder()
    
    # Get audio to test
    if audio_path is None:
        # Record from microphone
        audio, sample_rate = record_audio(duration=10)
        
        # Save to temporary file for preprocessing
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            write(tmp_path, sample_rate, audio)
            wav = preprocess_wav(tmp_path)
    else:
        # Load from file
        print(f"\nLoading audio from {audio_path}...")
        wav = preprocess_wav(audio_path)
    
    # Extract embedding from test audio
    print("Extracting voice embedding...")
    test_embedding = encoder.embed_utterance(wav)
    
    # Compare with each speaker in database
    print(f"\n{'='*50}")
    print("RESULTS:")
    print(f"{'='*50}")
    
    best_match = None
    best_similarity = -1
    
    for speaker_name, stored_embedding in speaker_db.items():
        similarity = compute_similarity(test_embedding, stored_embedding)
        
        match_status = "✓ MATCH" if similarity >= threshold else "✗ No match"
        print(f"\n{speaker_name}:")
        print(f"  Similarity: {similarity:.4f} ({similarity*100:.2f}%)")
        print(f"  Status: {match_status}")
        
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = speaker_name
    
    print(f"\n{'='*50}")
    if best_similarity >= threshold:
        print(f"✓ IDENTIFIED AS: {best_match}")
        print(f"  Confidence: {best_similarity*100:.2f}%")
    else:
        print(f"✗ UNKNOWN SPEAKER")
        print(f"  Best match: {best_match} ({best_similarity*100:.2f}%)")
        print(f"  Below threshold: {threshold*100:.2f}%")
    print(f"{'='*50}\n")
    
    return best_match, best_similarity

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test speaker recognition')
    parser.add_argument('--audio', '-a', type=str, default=None,
                       help='Path to audio file (if not provided, will record from mic)')
    parser.add_argument('--db', '-d', type=str, default='../Resources/speaker_db.pkl',
                       help='Path to speaker database file')
    parser.add_argument('--threshold', '-t', type=float, default=0.75,
                       help='Similarity threshold for matching (default: 0.75)')
    
    args = parser.parse_args()
    
    print("="*50)
    print("SPEAKER RECOGNITION TEST")
    print("="*50)
    
    test_speaker(
        audio_path=args.audio,
        speaker_db_path=args.db,
        threshold=args.threshold
    )