import json
from llm_client import LLMClient


class ActivityCoordinator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def check_intervention(
        self,
        history: list,
        plan: dict,
        current_step: dict,
        elapsed_minutes: float,
        vision_context: str = "",      # ← NEW: what the camera currently sees
    ) -> dict:
        """
        Checks whether the coordinator needs to intervene for:
          1. Time control  – end the activity when over budget
          2. Behaviour     – swearing, bullying, inappropriate content
          3. Student questions – off-topic questions that need a quick answer
        """
        target_duration_str = plan.get("approximate_duration", "10 minutes")
        try:
            target_duration = float(target_duration_str.split()[0])
        except Exception:
            target_duration = 10.0

        history_str = "\n".join(
            f"{e['role']}: {e['content']}" for e in history[-5:]
        )

        # Include vision context in the prompt when available
        vision_section = (
            f"\nCURRENT VISION CONTEXT:\n{vision_context}\n"
            if vision_context else ""
        )

        system_prompt = f"""You are the Activity Coordinator (Observer) for a child-robot interaction.
You monitor the conversation and intervene ONLY if necessary.

ROLES:
1. **Time Guardian**:
   - Target: {target_duration} minutes. Current: {elapsed_minutes:.1f} minutes.
   - If current time is > 90% of target and students are still in an 'open' phase, try to wrap up naturally.
   - If current time > target, you MUST intervene to end the activity politely but firmly.

2. **Behaviour Monitor**:
   - Detect swear words, bullying, or highly inappropriate behaviour.
   - If detected, provide a firm but gentle correction.
   - Use the vision context to note if a student appears upset or distressed.

3. **Question Answerer**:
   - If a student asks a direct question NOT part of the activity (e.g. "How old are you?"), answer it briefly.
   - Then bring focus back to the current activity.

CURRENT ACTIVITY CONTEXT:
- Title: {plan.get('activity_title', 'Activity')}
- Current Step Goal: {current_step.get('goal', 'N/A')}
{vision_section}
OUTPUT FORMAT (JSON ONLY):
{{
  "action": "continue" | "intervene",
  "response": "The robot's spoken response if intervening",
  "reason": "time" | "behaviour" | "question" | "none",
  "override_next_step": true | false
}}
"""

        user_prompt = (
            f"Recent History:\n{history_str}\n\n"
            "Decide if intervention is needed:"
        )

        try:
            response_str = self.llm_client.get_completion(
                system_prompt, user_prompt, json_mode=True
            )
            if "```json" in response_str:
                response_str = (
                    response_str.split("```json")[1].split("```")[0].strip()
                )
            return json.loads(response_str)
        except Exception as exc:
            return {"action": "continue", "reason": f"error: {str(exc)}"}