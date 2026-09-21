"""
Base activity class defining the lifecycle interface for all Gigi activities.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger("gigi.activities")


class BaseActivity(ABC):
    """
    Abstract base class for interactive Gigi applications and educational games.
    """

    def __init__(self, name: str, robot=None):
        self.name = name
        self.robot = robot
        self.is_running = False

    @abstractmethod
    def start(self) -> None:
        """Initializes assets, displays introductory screens, and begins the activity."""
        self.is_running = True

    @abstractmethod
    def stop(self) -> None:
        """Cleans up background threads, stops audio/movement, and returns robot to idle."""
        self.is_running = False

    def run(self) -> None:
        """Runs the complete activity from start to finish."""
        try:
            self.start()
        finally:
            self.stop()
