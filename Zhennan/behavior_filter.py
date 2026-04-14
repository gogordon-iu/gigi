"""
Offline behavior filter — no LLM needed.
Checks for swear words / bullying and returns a canned robot response.
Extend SWEAR_LIST and BULLY_PHRASES as needed.
"""

SWEAR_LIST = {
    "damn", "hell", "crap", "shit", "fuck", "ass", "bastard",
    "bitch", "piss", "dick", "cunt", "wtf", "stfu"
}

BULLY_PHRASES = [
    "shut up", "you're stupid", "you're dumb", "i hate you",
    "go away", "you suck", "you're ugly", "i don't like you"
]

CANNED_SWEAR_RESPONSE = "Let's use kind words while we play together!"
CANNED_BULLY_RESPONSE = "I feel sad when I hear that. Let's be kind to each other!"


def check_behavior(text: str) -> str | None:
    """
    Returns a canned robot response string if bad behavior is detected.
    Returns None if the input is clean.
    """
    lowered = text.lower()

    # Check swear words (word boundary match to avoid false positives)
    words = set(lowered.split())
    if words & SWEAR_LIST:
        return CANNED_SWEAR_RESPONSE

    # Check bullying phrases
    if any(phrase in lowered for phrase in BULLY_PHRASES):
        return CANNED_BULLY_RESPONSE

    return None