"""
Two-stage closing condition checker:

Stage 1 (offline) — keyword matching.
  Fast and free. Catches obvious cases like "done", "bye", "I choose X".
  If keywords clearly match → return True immediately, no LLM needed.

Stage 2 (LLM fallback) — binary YES/NO prompt to Qwen.
  Only called when keywords give no clear answer.
  Minimal prompt: closing condition + last 2 student turns → "YES" or "NO".
  No JSON, no reasoning, no explanation — just the answer.

This means the LLM is only called on ambiguous turns, not every turn.
"""

# High-confidence keyword rules only — obvious cases that don't need LLM.
# Intentionally kept small. Everything else falls through to Stage 2.
CONFIDENT_KEYWORD_MAP = {
    "said goodbye":  ["bye", "goodbye", "see you", "later", "good night"],
    "completed":     ["done", "finished", "i'm done", "all done", "ready"],
    "agreed":        ["yes", "sure", "okay", "ok", "agreed", "sounds good", "alright"],
}


def check_closing(
    history: list,
    closing_condition: str,
    llm_client,
    use_llm: bool = True
) -> bool:
    """
    Check whether the closing condition has been met.

    Args:
        history:           Full conversation history.
        closing_condition: The closing_condition string from the activity plan step.
        llm_client:        LLMClient instance (used only if stage 1 is inconclusive).
        use_llm:           Set False to disable LLM fallback entirely (pure offline).

    Returns:
        True if condition is met, False otherwise.
    """
    if not closing_condition:
        return False

    # ── Stage 1: keyword check (offline, free) ──────────────────────────────
    recent_student_text = " ".join(
        e["content"].lower()
        for e in history[-4:]
        if e.get("role") == "user"
    )

    if not recent_student_text:
        return False

    closing_lower = closing_condition.lower()

    for condition_key, trigger_words in CONFIDENT_KEYWORD_MAP.items():
        if condition_key in closing_lower:
            if any(kw in recent_student_text for kw in trigger_words):
                return True  # confident match — skip LLM

    # ── Stage 2: LLM fallback (only for ambiguous cases) ────────────────────
    if not use_llm or llm_client is None:
        return False

    return _llm_closing_check(history, closing_condition, llm_client)


def _llm_closing_check(history: list, closing_condition: str, llm_client) -> bool:
    """
    Ask the LLM a single binary question: has the closing condition been met?

    Prompt is kept as small as possible for Qwen 0.5B:
    - Only last 2 student utterances (not full history)
    - Condition stated once, plainly
    - Output: YES or NO only
    """
    recent_turns = [
        e["content"]
        for e in history[-6:]
        if e.get("role") == "user"
    ][-2:]

    if not recent_turns:
        return False

    recent_str = "\n".join(f"- {t}" for t in recent_turns)

    system_prompt = (
        "You decide if a condition has been met. "
        "Reply with ONLY the word YES or NO. Nothing else."
    )

    user_prompt = (
        f"Condition: {closing_condition}\n"
        f"Recent student replies:\n{recent_str}\n"
        "Has the condition been met? YES or NO:"
    )

    try:
        result = llm_client.get_completion(system_prompt, user_prompt, json_mode=False)
        return result and "YES" in result.strip().upper()
    except Exception:
        return False  # safe default: stay in the step