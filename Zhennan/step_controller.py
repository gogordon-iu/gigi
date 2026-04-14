"""
Offline step and time controller — no LLM needed.
Tracks elapsed time and signals when to wrap up or force-finish.
"""

import time


class StepController:
    def __init__(self, target_minutes: float):
        self.start_time = time.time()
        self.target_seconds = target_minutes * 60

    def elapsed_minutes(self) -> float:
        return (time.time() - self.start_time) / 60.0

    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def should_force_finish(self) -> bool:
        """True when we've exceeded the target duration."""
        return self.elapsed_seconds() > self.target_seconds

    def is_near_end(self) -> bool:
        """True when we're past 90% of target duration."""
        return self.elapsed_seconds() > (self.target_seconds * 0.9)

    def wrap_up_response(self) -> str:
        return "We're running low on time — you've done amazing work today, let's wrap up!"