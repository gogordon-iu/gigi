"""
Interaction and pedagogical framework for Gigi robot (formerly Zhennan module).
Coordinates activity planning, student turn-taking, and pedagogical strategies.
"""

from gigi.interaction.strategies import StrategyCatalog, Strategy
from gigi.interaction.safety_filter import check_behavior
from gigi.interaction.planner import ActivityPlanner
from gigi.interaction.manager import InteractionManager
from gigi.interaction.robot_interface import RobotInterface
from gigi.interaction.llm.client import LLMClient

__all__ = [
    "StrategyCatalog",
    "Strategy",
    "check_behavior",
    "ActivityPlanner",
    "InteractionManager",
    "RobotInterface",
    "LLMClient",
]
