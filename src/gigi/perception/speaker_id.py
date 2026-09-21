"""
Speaker identification and embedding extraction for Gigi robot.
Supports RKNN NPU hardware acceleration on Orange Pi and Resemblyzer CPU fallback.
"""

import os
import logging
from pathlib import Path
from typing import Optional
import numpy as np

from gigi.core.config import RESOURCES_DIR, USE_NPU_SPEAKER, IS_ROBOT

logger = logging.getLogger(__name__)


class VoiceEncoderRKNN:
    """
    RKNN implementation of Resemblyzer VoiceEncoder for the Orange Pi 5 Pro NPU.
    Loads a compiled 'voice-encoder.rknn' model and runs NPU inference.
    """

    def __init__(self, model_path: Optional[Path] = None):
        if model_path is None:
            model_path = RESOURCES_DIR / "voice-encoder.rknn"
        self.model_path = Path(model_path)
        self.rknn = None
        self.is_available = False

        if not self.model_path.exists():
            logger.warning(f"[Speaker Recognition] Model not found at {self.model_path}")
            return

        try:
            import logging as _py_logging

            _orig_nameToLevel = dict(_py_logging._nameToLevel)
            _orig_levelToName = dict(_py_logging._levelToName)
            from rknnlite.api import RKNNLite

            _py_logging._nameToLevel.update(_orig_nameToLevel)
            _py_logging._levelToName.update(_orig_levelToName)
            self.rknn = RKNNLite()
            ret = self.rknn.load_rknn(str(self.model_path))
            if ret != 0:
                raise RuntimeError(f"Failed to load VoiceEncoder RKNN model (code {ret})")
            ret = self.rknn.init_runtime()
            if ret != 0:
                raise RuntimeError(f"Failed to init RKNN runtime (code {ret})")
            self.is_available = True
            logger.info(f"[Speaker Recognition] VoiceEncoder RKNN loaded from {self.model_path.name}")
        except Exception as e:
            logger.warning(f"[Speaker Recognition] Could not load NPU VoiceEncoder: {e}")

    def embed_utterance(self, wav: np.ndarray) -> np.ndarray:
        """Extract speaker embedding vector (256-dim) from processed wav using RKNN NPU."""
        if not self.is_available or self.rknn is None:
            return np.zeros(256, dtype=np.float32)

        try:
            from resemblyzer.audio import wav_to_mel_spectrogram

            mel = wav_to_mel_spectrogram(wav)
            feats = mel[np.newaxis, :, :].astype(np.float32)
            outputs = self.rknn.inference(inputs=[feats])
            if outputs is None or len(outputs) == 0:
                return np.zeros(256, dtype=np.float32)

            embedding = outputs[0].flatten().copy()
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            logger.error(f"[Speaker Recognition] NPU inference error: {e}")
            return np.zeros(256, dtype=np.float32)

    def release(self) -> None:
        if self.rknn is not None:
            try:
                self.rknn.release()
            except Exception:
                pass
            self.rknn = None
            self.is_available = False

    def __del__(self):
        self.release()


def get_speaker_encoder():
    """Factory returning the optimal speaker encoder for the current platform."""
    if IS_ROBOT and USE_NPU_SPEAKER:
        encoder = VoiceEncoderRKNN()
        if encoder.is_available:
            return encoder

    try:
        from resemblyzer import VoiceEncoder

        logger.info("[Speaker Recognition] Using CPU PyTorch VoiceEncoder")
        return VoiceEncoder()
    except ImportError:
        logger.warning("[Speaker Recognition] Resemblyzer not installed, speaker identification unavailable.")
        return None


class SpeakerDatabase:
    """Stores speaker embeddings alongside names and transcription history."""

    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = RESOURCES_DIR / "speaker_db.pkl"
        else:
            self.db_path = Path(db_path)
        self.speaker_data = {}  # {name: embedding}
        self.transcription_records = {}  # {name: [{"timestamp": float, "formatted_time": str, "text": str}]}
        self.load_database()

    def load_database(self):
        """Load speaker database from disk, supporting both old and new formats."""
        import pickle

        if self.db_path.exists():
            try:
                with open(self.db_path, "rb") as f:
                    data = pickle.load(f)
                if isinstance(data, dict):
                    if "embeddings" in data:
                        self.speaker_data = data["embeddings"]
                        self.transcription_records = data.get("transcriptions", {})
                    else:
                        self.speaker_data = data
                        self.transcription_records = {}
                else:
                    self.speaker_data = {}
                    self.transcription_records = {}
                logger.info(f"[Speaker DB] Loaded {len(self.speaker_data)} profiles from {self.db_path}")
            except Exception as e:
                logger.warning(f"Error loading speaker database: {e}")
                self.speaker_data = {}
                self.transcription_records = {}
        else:
            logger.info(f"No existing speaker database found at {self.db_path}")

    def save_database(self):
        """Save speaker database to disk."""
        import pickle

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, "wb") as f:
                data = {
                    "embeddings": self.speaker_data,
                    "transcriptions": self.transcription_records,
                }
                pickle.dump(data, f)
            logger.info(f"[Speaker DB] Saved database to {self.db_path}")
        except Exception as e:
            logger.error(f"Error saving speaker database: {e}")

    def add_speaker(self, name, embedding):
        """Add or update a speaker embedding."""
        self.speaker_data[name] = embedding
        self.save_database()

    def add_transcription_record(self, name, text):
        """Add a time-stamped transcription record for the recognized speaker."""
        import time

        if not name or not text or not text.strip():
            return
        if name not in self.transcription_records:
            self.transcription_records[name] = []

        record = {
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "text": text.strip(),
        }
        self.transcription_records[name].append(record)
        self.save_database()

    def identify_speaker(self, embedding, threshold=0.75):
        """Identify speaker from embedding."""
        if not self.speaker_data:
            return None, 0

        try:
            from scipy.spatial.distance import cosine
            has_scipy = True
        except ImportError:
            has_scipy = False

        best_match = None
        best_similarity = 0.0

        for name, stored_embedding in self.speaker_data.items():
            if has_scipy:
                similarity = float(1.0 - cosine(embedding, stored_embedding))
            else:
                norm_a = np.linalg.norm(embedding)
                norm_b = np.linalg.norm(stored_embedding)
                if norm_a > 0 and norm_b > 0:
                    similarity = float(np.dot(embedding, stored_embedding) / (norm_a * norm_b))
                else:
                    similarity = 0.0

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name

        if best_similarity >= threshold:
            return best_match, best_similarity
        return None, best_similarity

