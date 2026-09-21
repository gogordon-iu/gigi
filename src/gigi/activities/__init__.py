"""
Interactive activities, educational tutors, and games for Gigi robot.
"""

from gigi.activities.base import BaseActivity
from gigi.activities.common.tracker import BackgroundFaceTracker
from gigi.activities.common.utils import extract_name

__all__ = [
    "BaseActivity",
    "BackgroundFaceTracker",
    "extract_name",
]
