"""
Interactive activities, educational tutors, and games for Gigi robot.
"""

from gigi.activities.base import BaseActivity
from gigi.activities.common.tracker import BackgroundFaceTracker
from gigi.activities.common.utils import extract_name
from gigi.activities.mastermind.mastermind import MastermindActivity
from gigi.activities.math_quest.math_quest import MathQuestActivity
from gigi.activities.story_game.story_game import StoryGameActivity
from gigi.activities.social.make_friends import MakeFriendsActivity

__all__ = [
    "BaseActivity",
    "BackgroundFaceTracker",
    "extract_name",
    "MastermindActivity",
    "MathQuestActivity",
    "StoryGameActivity",
    "MakeFriendsActivity",
]
