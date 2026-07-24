import json
import re

def remove_trailing_questions(text: str) -> str:
    """
    If the text contains multiple sentences and the last sentence ends with a question mark,
    removes that last sentence. Otherwise, if the whole text is a question, replaces it
    with a default transition statement.
    """
    text = text.strip()
    if not text:
        return text
    # Split on sentence boundaries (. ! ?) followed by whitespace or string end
    sentences = re.split(r'(?<=[.!?])\s+', text)
    while sentences and sentences[-1].strip().endswith('?'):
        sentences.pop()
    cleaned = " ".join(s.strip() for s in sentences if s.strip())
    if not cleaned:
        cleaned = "Let's move on to the next step."
    return cleaned

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

        # Extract a short description of the current topic to guide the transition
        topic_desc = step.get("image_prompt", "")
        if len(topic_desc) > 80:
            topic_desc = topic_desc[:77] + "..."

        system_prompt = f"""You are Gigi, a friendly educational robot talking to an 8-year-old student.
Speak in the first person ("I", "my"). You are the speaker.
RULES:
1. Never say the name "Gigi" or refer to yourself by name.
2. Reply directly to the student's last message in 1 warm sentence (no question marks).
3. Transition naturally towards the next step: {topic_desc}"""

        user_prompt = f"""Recent History:
{history_str}

"""
        if vision_context:
            user_prompt += f"{vision_context}\n\n"

        user_prompt += "Generate Robot Response:"

        response = self.conversation.get_response(system_prompt, user_prompt)
        response = remove_trailing_questions(response)
        return response
