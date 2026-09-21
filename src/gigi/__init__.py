"""
Gigi: An Open-Source Social Robot Platform
==========================================

Gigi is an expressive social robot platform designed for educational,
interactive, and child-robot interaction (CRI/HRI) applications.
"""

__version__ = "0.2.0"
__author__ = "Gigi Robotics Team"

# Lazy or direct package-level imports
try:
    from gigi.core.robot import GigiRobot
except ImportError:
    pass
