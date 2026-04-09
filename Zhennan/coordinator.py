import json
# from Zhennan.llm_client_azure import LLMClient
from llm_client import LLMClient

class ActivityCoordinator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def check_intervention(self, history: list, plan: dict, current_step: dict, elapsed_minutes: float) -> dict:
        """
        Checks if the coordinator needs to intervene for:
        1. Time control (ending the activity naturally)
        2. Inappropriate behavior (swearing, being mean)
        3. Student questions (answering them before resuming)
        """
        
        target_duration_str = plan.get("approximate_duration", "10 minutes")
        # Extract number from "10 minutes"
        try:
            target_duration = float(target_duration_str.split()[0])
        except:
            target_duration = 10.0

        # Keep last few turns for context
        history_str = "\n".join([f"{entry['role']}: {entry['content']}" for entry in history[-5:]])
        
        system_prompt = f"""You are the Activity Coordinator (Observer) for a child-robot interaction.
You monitor the conversation and intervene ONLY if necessary.

ROLES:
1. **Time Guardian**:
   - Target: {target_duration} minutes. Current: {elapsed_minutes:.1f} minutes.
   - If current time is > 90% of target, and students are still in an 'open' phase, try to wrap up naturally.
   - If current time > target, you MUST intervene to end the activity politely but firmly.

2. **Behavior Monitor**:
   - Detect swear words, bullying, or highly inappropriate behavior.
   - If detected, provide a firm but gentle correction (e.g., "Let's use kind words while we play together!").

3. **Question Answerer**:
   - If a student asks a direct question that is NOT part of the activity tasks (e.g., "How old are you?", "Why is the sky blue?"), answer it briefly.
   - Then, bring the focus back to the current activity.

CURRENT ACTIVITY CONTEXT:
- Title: {plan.get('activity_title', 'Activity')}
- Current Step Goal: {current_step.get('goal', 'N/A')}

OUTPUT FORMAT (JSON ONLY):
{{
  "action": "continue" | "intervene",
  "response": "The robot's spoken response if intervening",
  "reason": "time" | "behavior" | "question" | "none",
  "override_next_step": true | false (Set true if we should skip to the final conclusion because of time)
}}
"""

        user_prompt = f"Recent History:\n{history_str}\n\nDecide if intervention is needed:"
        
        try:
            response_str = self.llm_client.get_completion(system_prompt, user_prompt, json_mode=True)
            # Sometimes LLM might wrap in ```json ... ```
            if "```json" in response_str:
                response_str = response_str.split("```json")[1].split("```")[0].strip()
            return json.loads(response_str)
        except Exception as e:
            # Fallback to continue if LLM fails
            return {"action": "continue", "reason": f"error: {str(e)}"}
