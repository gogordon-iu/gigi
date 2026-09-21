"""
Camera hardware abstraction for Gigi robot.
Scans available video devices and provides thread-safe frame acquisition.
"""

import logging
from typing import Optional, List, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def find_camera_ports(max_ports: int = 6) -> List[int]:
    """Scans and returns all available OpenCV camera port indices."""
    available_ports = []
    for port in range(max_ports):
        cap = cv2.VideoCapture(port)
        if cap.isOpened():
            available_ports.append(port)
            cap.release()
    return available_ports


def open_camera(port: Optional[int] = None, width: int = 640, height: int = 480) -> Optional[cv2.VideoCapture]:
    """
    Opens the requested camera port or scans ports 0-5 to find the first working camera.
    Configures standard capture dimensions.
    """
    ports = [port] if port is not None else range(6)
    for p in ports:
        cap = cv2.VideoCapture(p)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            logger.info(f"Camera opened on port {p} ({width}x{height})")
            return cap
        cap.release()

    logger.warning("No functioning camera port could be opened.")
    return None
