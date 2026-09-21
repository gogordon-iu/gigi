"""
Dedicated Verification & Diagnostic Package for Gigi robot subsystems.
"""

from gigi.verification.cli import (
    run_verification,
    test_camera,
    test_motors,
    test_gestures,
    test_screen,
    test_audio,
    test_mic,
    test_face,
    test_llm,
)

__all__ = [
    "run_verification",
    "test_camera",
    "test_motors",
    "test_gestures",
    "test_screen",
    "test_audio",
    "test_mic",
    "test_face",
    "test_llm",
]
