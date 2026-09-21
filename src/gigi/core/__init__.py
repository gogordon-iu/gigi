"""
Core robot lifecycle, configuration, logging, and daemon services for Gigi.
"""

from gigi.core.config import (
    IS_ROBOT,
    PROJECT_ROOT,
    ASSETS_DIR,
    RESOURCES_DIR,
    SETUP_DIR,
    DATA_DIR,
)
from gigi.core.logger import InteractionLogger
from gigi.core.robot import GigiRobot, Character

__all__ = [
    "GigiRobot",
    "Character",
    "InteractionLogger",
    "IS_ROBOT",
    "PROJECT_ROOT",
    "ASSETS_DIR",
    "RESOURCES_DIR",
    "SETUP_DIR",
    "DATA_DIR",
]
