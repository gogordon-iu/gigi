"""
Common helper functions for Gigi activities (name extraction, greeting parsing).
"""

import re
from typing import Optional


def extract_name(text: str, robot=None) -> str:
    """
    Extracts a person's name from spoken input using LLM first, falling back to regex.
    """
    if not text or not text.strip():
        return "Friend"

    # Try LLM extraction if robot conversation available
    if robot and hasattr(robot, "conversation") and robot.conversation:
        try:
            system_prompt = (
                "You are a name extraction assistant. Return ONLY the person's first name, capitalized. "
                "If the text does not contain a name, output 'Friend'."
            )
            user_prompt = f"Extract the name: '{text}'"
            response = robot.conversation.get_response(system_prompt=system_prompt, user_prompt=user_prompt)
            extracted = response.strip().replace(".", "").replace("!", "").replace("?", "")
            if extracted and len(extracted.split()) == 1 and extracted.lower() not in ["friend", "unknown"]:
                return extracted.capitalize()
        except Exception:
            pass

    # Regex fallback
    clean = re.sub(r"[^\w\s]", "", text).strip()
    weird_words = {"it", "this", "that", "yes", "no", "hello", "the", "what", "robot", "is", "me", "hi"}
    patterns = [r"\bmy name is\s+(\w+)", r"\bi am\s+(\w+)", r"\bcall me\s+(\w+)", r"\bthis is\s+(\w+)"]
    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m and m.group(1).lower() not in weird_words:
            return m.group(1).capitalize()

    words = clean.split()
    if words and len(words) <= 3 and words[-1].lower() not in weird_words:
        return words[-1].capitalize()

    return "Friend"
