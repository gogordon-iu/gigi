"""
Shared face tracking utilities for activities and educational games.
"""

import threading
import logging

logger = logging.getLogger("gigi.activities.tracker")


class BackgroundFaceTracker:
    """
    Manages active face follow tracking in a background thread during activities.
    """

    def __init__(self, robot):
        self.robot = robot
        self.stop_event = threading.Event()
        self.thread = None

    def start(self) -> None:
        if not self.robot or not self.robot.vision:
            logger.info("Vision is disabled or robot unavailable; cannot start face tracking.")
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self.robot.follow_face,
            kwargs={"stop_event": self.stop_event},
            daemon=True,
        )
        self.thread.start()
        logger.info("Background face follow tracker started.")

    def stop(self) -> None:
        if self.thread:
            self.stop_event.set()
            self.thread.join(timeout=1.5)
            self.thread = None
            logger.info("Background face follow tracker stopped.")
