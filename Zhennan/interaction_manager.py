"""
InteractionManager — simplified for Qwen 0.5B.

Strategy is selected OFFLINE via StrategyRAG (no LLM cost).
The LLM receives a minimal prompt (~100-150 tokens) and is asked
for ONE short spoken sentence only.
"""

import re
from llm_client import LLMClient
from StrategyRAG import StrategyRAG


def _first_sentence(text: str) -> str:
    """
    Return only the first sentence of the model's output.
    Prevents the model from hallucinating extra turns like:
      "Great job! student: can we do more? robot: yes!"
    Also strips any echoed role prefix (robot: / assistant:).
    """
    # Strip echoed role prefix
    text = re.sub(r"^(robot:|assistant:|student:)\s*", "", text.strip(), flags=re.IGNORECASE)

    # Cut at the first sentence boundary
    m = re.search(r"[.!?]", text)
    if m:
        text = text[:m.end()].strip()

    # If the model started hallucinating a new turn, cut there too
    text = re.split(r"\n\s*(student:|robot:|user:|assistant:)", text, flags=re.IGNORECASE)[0]

    return text.strip()


class InteractionManager:
    def __init__(self, llm_client: LLMClient, strategy_rag: StrategyRAG):
        self.llm_client = llm_client
        self.rag = strategy_rag

    def _build_prompts(self, history: list, step: dict, student_input: str) -> tuple[str, str]:
        """
        Shared prompt builder used by both get_prompts and generate_turn.

        Key fix: ALL role labels are normalized to "student"/"robot".
        Previously history used "user"/"assistant" while the prompt
        used "student"/"robot" — the mixed labels caused 0.5B to
        hallucinate the rest of the conversation itself.
        """
        # RAG: pick best strategy offline
        best_strategies = self.rag.retrieve(student_input or "", top_k=1)
        strategy = best_strategies[0] if best_strategies else None
        strategy_hint = strategy.robot_actions if strategy else ""
        strategy_id   = strategy.id if strategy else "none"

        # Only last 2 turns — normalize roles to student/robot
        recent = history[-2:]
        history_lines = []
        for e in recent:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        step_goal = step.get("goal", "")

        system_prompt = (
            f"You are a friendly educational robot talking to a child. "
            f"Goal: {step_goal}. "
            f"Hint: {strategy_hint} "
            f"Reply with ONE short sentence only. Stop after the sentence."
        )

        user_prompt = (
            f"{history_str}\n"
            f"student: {student_input}\n"
            f"robot:"
        )

        return system_prompt, user_prompt, strategy_id

    def get_prompts(self, history: list, step: dict, student_input: str = "") -> tuple[str, str]:
        """
        Returns (system_prompt, user_prompt) for external callers (e.g. gigi.conversation).
        """
        system_prompt, user_prompt, _ = self._build_prompts(history, step, student_input)
        return system_prompt, user_prompt

    def generate_turn(self, history: list, step: dict, student_input: str) -> tuple[str, str]:
        """
        Generate the robot's next spoken response.

        Returns:
            (response_text, strategy_id)
        """
        system_prompt, user_prompt, strategy_id = self._build_prompts(history, step, student_input)

        response = self.llm_client.get_completion(system_prompt, user_prompt, json_mode=False)

        # Take only the first sentence — stops hallucinated multi-turn output
        response = _first_sentence(response)

        return response, strategy_id