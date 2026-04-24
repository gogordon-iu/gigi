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
        # Keep last 2 turns for context
        history_lines = []
        for e in history[-2:]:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a child.
CURRENT STEP: {json.dumps(step, indent=2)}

STRATEGY CATALOG:
{catalog_str}

YOUR ROLE:
1. Analyze the student's input in the context of the current step.
2. IF the step type is "open":
    - Check the "closing_condition". If it is met based on the history, output exactly: [NEXT_STEP]
    - Otherwise, determine if any strategy from the catalog is triggered.
    - If a strategy matches, use its 'robot_actions' as a guide.
    - Keep the conversation flowing naturally towards the step's goal.
3. IF the step type is "canned":
    - This function should typically not be called for canned steps as they are static.
    - However, if called, just output the robot_script or a transition.

OUTPUT FORMAT (MANDATORY):
- If the conversation should end or move forward: [NEXT_STEP] (You can still include a robot response before this tag).
- For EVERY response in "open" step, you MUST try to apply at least one strategy from the CATALOG.
- VARIETY IS KEY: Avoid using the same strategy multiple times in a row. Look at the interaction history and choose a DIFFERENT approach if the situation allows.
- If a strategy is applied, prefix your response with exactly: [STRATEGY: strategy_id]
- Include appropriate non-verbal actions in square brackets (e.g., [nod], [wave hands]) within or after the spoken text, following the 'Non-Verbal Options' in the catalog.
- Example: [STRATEGY: express_enthusiasm_for_learning] [wave hands] I'm so excited to see what you create! [smile]
- If absolutely no strategy fits, you may output just the spoken text.
- DO NOT use IDs that are not present in the provided STRATEGY CATALOG.
- Reply with ONE short conversational sentence.
- Stop immediately after the first sentence.
"""
        
        user_prompt = f"Recent Interaction History:\n{history_str}\n\n"
        if vision_context:
            user_prompt += f"{vision_context}\n"
        
        student_said = history[-1]['content'] if history and history[-1]['role'] == 'user' else '...'
        user_prompt += f"Student just said: {student_said}\n\nGenerate Robot Response:"

        # The conversation.get_response method handles RAG retrieval and sentence truncation internally.
        response = self.conversation.get_response(system_prompt, user_prompt)
        return response