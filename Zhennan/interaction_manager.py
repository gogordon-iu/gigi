"""
InteractionManager — simplified for Qwen 0.5B.

Strategy is selected OFFLINE via StrategyRAG (no LLM cost).
The LLM receives a minimal prompt (~100-150 tokens) and is asked
for ONE short spoken sentence only.
"""

import re
from llm_client import LLMClient


def first_sentence(text: str) -> str:
    """
    Return only the first sentence of the model's output.

    Prevents the model from:
      - Hallucinating extra turns ("student: ... robot: ...")
      - Producing numbered lists or bullet points
      - Echoing its own role prefix
    """
    # Strip echoed role prefix
    text = re.sub(r"^(robot:|assistant:|student:|gigi:)\s*", "", text.strip(), flags=re.IGNORECASE)

    # Strip markdown bullets/numbering if the model opened with one
    text = re.sub(r"^\s*(\d+\.|[-*•])\s*", "", text)

    # Cut at the first sentence boundary
    m = re.search(r"[.!?]", text)
    if m:
        text = text[:m.end()].strip()

    # If the model started hallucinating a new turn, cut there too
    text = re.split(r"\n\s*(student:|robot:|user:|assistant:|gigi:)", text, flags=re.IGNORECASE)[0]

    # If nothing usable remains, return a safe fallback
    return text.strip() or "That's really interesting — tell me more!"


class InteractionManager:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def _build_prompts(self, history: list, step: dict, student_input: str) -> tuple[str, str]:
        """
        Shared prompt builder.

        All role labels are normalized to "student"/"robot" so the
        0.5B model doesn't get confused by mixed "user"/"assistant" labels.
        """
        # Only last 2 turns — normalize roles to student/robot
        recent = history[-2:]
        history_lines = []
        for e in recent:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        step_goal = step.get("goal", "")

        system_prompt = (
            f"You are Gigi, a friendly educational robot talking to a child. "
            f"Goal: {step_goal}. "
            f"Reply with ONE short conversational sentence. "
            f"Do NOT use lists, bullet points, or numbers. "
            f"Do NOT explain or give multiple ideas. "
            f"Speak naturally like you are talking out loud. "
            f"Stop immediately after the first sentence."
        )

        user_prompt = (
            f"{history_str}\n"
            f"student: {student_input}\n"
            f"robot:"
        )

        return system_prompt, user_prompt

    def get_prompts(self, history: list, step: dict, student_input: str = "") -> tuple[str, str]:
        """
        Returns (system_prompt, user_prompt) for external callers.
        The caller is responsible for passing the response through
        first_sentence() before speaking it.
        """
        return self._build_prompts(history, step, student_input)

    def generate_turn(self, history: list, step: dict, student_input: str) -> str:
        """
        Generate the robot's next spoken response directly via LLMClient.
        Applies first_sentence() truncation internally.
        """
        system_prompt, user_prompt = self._build_prompts(history, step, student_input)
        response = self.llm_client.get_completion(system_prompt, user_prompt, json_mode=False)
        return first_sentence(response)