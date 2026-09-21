"""
Perception modules for Gigi robot (vision, face recognition, emotion, hearing, STT, speaker ID, pronunciation).
"""

from gigi.perception.vision_helper import FaceDatabase, EmotionDetector
from gigi.perception.vision import Vision
from gigi.perception.hearing import Hearing
from gigi.perception.pronunciation import CitrinetGOP
from gigi.perception.speaker_id import VoiceEncoderRKNN, get_speaker_encoder

__all__ = [
    "FaceDatabase",
    "EmotionDetector",
    "Vision",
    "Hearing",
    "CitrinetGOP",
    "VoiceEncoderRKNN",
    "get_speaker_encoder",
]
