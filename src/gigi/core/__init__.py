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


def __getattr__(name):
    if name in ("GigiRobot", "Character"):
        from gigi.core.robot import GigiRobot, Character
        return GigiRobot if name == "GigiRobot" else Character
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
