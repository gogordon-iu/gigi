import json
import re
from strategy_catalog import StrategyCatalog

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

        closing_cond = step.get("closing_condition", "")
        topic_desc = step.get("image_prompt", "")
        if len(topic_desc) > 80:
            topic_desc = topic_desc[:77] + "..."

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a child.
Speak in the first person ("I", "my"). You are the speaker.
RULES:
1. Never say the name "Gigi" or refer to yourself by name.
2. Reply directly to the child in 1 or 2 short sentences.
3. If the closing condition is met (Condition: {closing_cond}), say a closing sentence and add: [NEXT_STEP]
Otherwise, continue the conversation.

Step Topic: {topic_desc}"""

        user_prompt = f"""Recent History:
{history_str}

"""
        if vision_context:
            user_prompt += f"{vision_context}\n\n"

        user_prompt += "Generate Robot Response:"

        # The conversation.get_response method handles RAG retrieval and sentence truncation internally.
        response = self.conversation.get_response(system_prompt, user_prompt)
        
        # Strip trailing questions if the response transitions to the next step
        next_step_match = re.search(r"\[NEXT[ _]STEP\]", response, re.IGNORECASE)
        if next_step_match:
            pre_text = response[:next_step_match.start()].strip()
            tag = next_step_match.group(0)
            post_text = response[next_step_match.end():].strip()
            
            cleaned_pre = remove_trailing_questions(pre_text)
            response = f"{cleaned_pre} {tag}"
            if post_text:
                cleaned_post = remove_trailing_questions(post_text)
                if cleaned_post:
                    response = f"{cleaned_pre} {tag} {cleaned_post}"
            response = response.strip()
            
        return response
