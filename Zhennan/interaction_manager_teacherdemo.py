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
        # Create a cleaned version of the step without the fields we don't want the LLM to see
        clean_step = {k: v for k, v in step.items() if k not in ["goal", "closing_condition", "suggested_topics"]}

        # Keep last 6 turns for context
        history_lines = []
        for e in history[-6:]:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a 3rd grade student (8-9 years old).
Keep your vocabulary simple, engaging, and age-appropriate.
CURRENT STEP: {json.dumps(clean_step, indent=2)}

YOUR ROLE:
1. Briefly acknowledge and appreciate the student based on their response.
2. Do not ask the student any questions.

MANDATORY OUTPUT RULES:
- EXTREMELY SHORT: Reply with MAXIMUM 15 words.
- ONLY ONE SENTENCE.
- DO NOT use lists, bullet points, or paragraphs.
- Speak naturally like you are talking out loud.
- Include non-verbal actions in square brackets (e.g., [smile], [nod]).
"""
        
        user_prompt = f"Recent Interaction History:\n{history_str}\n\n"
        if vision_context:
            user_prompt += f"{vision_context}\n"
        
        user_prompt += "\nGenerate Robot Response:"

        response = self.conversation.get_response(system_prompt, user_prompt)
        return response
