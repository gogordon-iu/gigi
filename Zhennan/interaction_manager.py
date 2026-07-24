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

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a child.
Speak in the first person ("I", "my", "we"). You are the speaker.
CRITICAL PERSONALITY RULES:
- Never address yourself by name ("Gigi"). Do NOT start your response with "Gigi, ..." or mention "Gigi" as a separate person.
- Respond directly and warmly in the first person to what the child just said, and transition smoothly.
- Keep your vocabulary simple, engaging, and age-appropriate.

CURRENT STEP: {json.dumps(step, indent=2)}

YOUR ROLE:
1. First, check the "closing_condition" below. 
2. IF the condition is met:
    - Say a quick closing sentence (e.g. "Great job! Let's move on.") and then output exactly: [NEXT_STEP]
3. IF the condition is NOT met:
    - Keep the conversation flowing naturally towards the closing condition.

MANDATORY OUTPUT RULES:
- Reply with ONLY ONE or TWO short spoken sentences.
- Use the EXACT tag [NEXT_STEP] to move forward.
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
