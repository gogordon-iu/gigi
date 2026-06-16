"""
ActivityCoordinator — DEPRECATED for Qwen 0.5B deployments.

All coordination logic (time control, behavior checking, closing conditions)
has been moved to offline modules:
    - behavior_filter.py   → swear/bully detection
    - step_controller.py   → time tracking
    - closing_checker.py   → closing condition keyword matching

This class is kept as a stub for backward compatibility.
Set IS_COORDINATOR = False in run_activity.py (already the default).
"""


class ActivityCoordinator:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        print("[ActivityCoordinator] WARNING: Coordinator is disabled. "
              "All coordination is handled offline. Set IS_COORDINATOR=False.")

    def check_intervention(self, *args, **kwargs) -> dict:
        """Stub — always returns continue. Use offline modules instead."""
        return {"action": "continue", "reason": "none"}