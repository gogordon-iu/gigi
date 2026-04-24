import json

class InteractionManager:
    def __init__(self, conversation, strategy_catalog=None):
        """
        Initializes the InteractionManager for the teacher demo.
        """
        self.conversation = conversation

    def generate_turn(self, history: list, step: dict, vision_context: str = None) -> str:
        """
        Generates a single acknowledgment and then moves to the next step.
        """
        # Keep last 6 turns for context
        history_lines = []
        for e in history[-6:]:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a child.
CURRENT STEP: {json.dumps(step, indent=2)}

YOUR ROLE:
1. Briefly acknowledge and appreciate or encourage the student based on their response.
2. After your brief acknowledgment, you MUST output exactly: [NEXT_STEP]

MANDATORY OUTPUT RULES:
- Reply with ONLY ONE short spoken sentence.
- Use the EXACT tag [NEXT_STEP] at the end of your response to move forward.
- DO NOT use lists, bullet points, or numbering.
- Speak naturally like you are talking out loud.
- Include non-verbal actions in square brackets (e.g., [smile], [nod]).
"""
        
        user_prompt = f"Recent Interaction History:\n{history_str}\n\n"
        if vision_context:
            user_prompt += f"{vision_context}\n"
        
        user_prompt += "\nGenerate Robot Response:"

        response = self.conversation.get_response(system_prompt, user_prompt)
        return response
