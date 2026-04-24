import json
import re
from strategy_catalog import StrategyCatalog

class InteractionManager:
    def __init__(self, conversation, strategy_catalog: StrategyCatalog):
        """
        Initializes the InteractionManager.
        
        Args:
            conversation: An instance of Character.conversation.Conversation.
            strategy_catalog: An instance of StrategyCatalog.
        """
        self.conversation = conversation
        self.strategy_catalog = strategy_catalog

    def generate_turn(self, history: list, step: dict, vision_context: str = None) -> str:
        """
        Generates the next robot turn based on history, the current step, and optional vision context.
        """
        catalog_str = self.strategy_catalog.get_randomized_catalog_string()
        
        # Serialize history for prompt
        # Keep last 6 turns for context (3 exchanges)
        history_lines = []
        for e in history[-6:]:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a child.
CURRENT STEP: {json.dumps(step, indent=2)}

YOUR ROLE:
1. Analyze the student's input in the context of the current step.
2. IF the step type is "open":
    - Check the "closing_condition". If it is met based on the history, output exactly: [NEXT_STEP]
    - Otherwise, keep the conversation flowing naturally towards the goal.
3. IF the step type is "canned":
    - This function should typically not be called for canned steps as they are static.
    - However, if called, just output the robot_script or a transition.

MANDATORY OUTPUT RULES:
- Reply with ONLY ONE or TWO short spoken sentences.
- DO NOT use lists, bullet points, or numbering.
- DO NOT give multiple points or long explanations.
- Speak naturally like you are talking out loud.
- Include non-verbal actions in square brackets (e.g., [nod], [wave hands]).
- Stop immediately after the first or second sentence.
"""
        
        user_prompt = f"Recent Interaction History:\n{history_str}\n\n"
        if vision_context:
            user_prompt += f"{vision_context}\n"
        
        user_prompt += "\nGenerate Robot Response:"

        # The conversation.get_response method handles RAG retrieval and sentence truncation internally.
        response = self.conversation.get_response(system_prompt, user_prompt)
        return response
