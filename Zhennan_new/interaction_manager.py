import json
from strategy_catalog import StrategyCatalog

class InteractionManager:
    def __init__(self, conversation, strategy_catalog: StrategyCatalog):
        self.conversation = conversation
        self.strategy_catalog = strategy_catalog

    def generate_turn(self, history: list, step: dict) -> str:
        """
        Generates the next robot turn based on history and the current step.
        """
        catalog_str = self.strategy_catalog.get_randomized_catalog_string()
        
        # Serialize history for prompt
        history_str = "\n".join([f"{entry['role']}: {entry['content']}" for entry in history[-10:]]) # Keep last 10 turns for context

        system_prompt = f"""You are an educational robot facilitating an activity.
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
"""
        
        user_prompt = f"Recent Interaction History:\n{history_str}\n\nStudent just said: {history[-1]['content'] if history and history[-1]['role'] == 'student' else '...'}\n\nGenerate Robot Response:"

        response = self.conversation.get_response(system_prompt, user_prompt)
        return response
