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
        # Create a cleaned version of the step without the fields we don't want the LLM to see
        clean_step = {k: v for k, v in step.items() if k not in ["goal", "closing_condition", "suggested_topics"]}

        # Keep last 6 turns for context
        history_lines = []
        for e in history[-6:]:
            role = "student" if e["role"] == "user" else "robot"
            history_lines.append(f"{role}: {e['content']}")
        history_str = "\n".join(history_lines)

        system_prompt = f"""You are Gigi, a friendly educational robot talking to a 3rd grade student (8-9 years old).
Speak in the first person ("I", "my", "we"). You are the speaker.
CRITICAL PERSONALITY RULES:
- Never address yourself by name ("Gigi"). Do NOT start your response with "Gigi, ..." or mention "Gigi" as a separate person.
- Respond directly and warmly in the first person to what the student just said (e.g. "I love looking at trees too!").
- Keep your vocabulary simple, engaging, and age-appropriate.

CURRENT STEP DETAILS:
{json.dumps(clean_step, indent=2)}"""

        user_prompt = f"""Recent Interaction History:
{history_str}

"""
        if vision_context:
            user_prompt += f"{vision_context}\n\n"

        user_prompt += """Above is the interaction history between you and the student. I gave you this to understand the context.
 
YOUR ROLE:
1. Respond to what the student just said in the first person, acknowledging and appreciating their thoughts (e.g., "I think that's a wonderful idea!").
2. Connect your response smoothly to a continuation towards the next step/topic described in the CURRENT STEP DETAILS.
3. Do not ask the student to do anything or speak anything. Just appreciate and transition.
4. The response must not have any questions or end with a question mark.
 
MANDATORY OUTPUT RULES of the response:
- Reply with MAXIMUM ONE or TWO short sentences.
- DO NOT use lists, bullet points, or paragraphs.
- DO NOT ask follow up questions or responses which ends with QUESTION MARKS.
- Speak naturally like you are talking out loud.
- Include non-verbal actions in square brackets (e.g., [smile], [nod]).
 
These are the output rules you must follow at any cost. You'll be rewarded if you follow these rules.
 
Generate the response:"""

        response = self.conversation.get_response(system_prompt, user_prompt)
        response = remove_trailing_questions(response)
        return response
