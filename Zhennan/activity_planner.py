import json
# from Zhennan.llm_client_azure import LLMClient
from llm_client import LLMClient
from strategy_catalog import StrategyCatalog

class ActivityPlanner:
    def __init__(self, llm_client: LLMClient, strategy_catalog: StrategyCatalog):
        self.llm_client = llm_client
        self.strategy_catalog = strategy_catalog

    def generate_plan(self, activity_description: str) -> dict:
        """
        Generates a structured activity plan based on the user's description.
        """
        catalog_str = self.strategy_catalog.to_string()
        
        system_prompt = f"""You are an expert educational robot activity designer.
Your goal is to transform a brief activity description into a structured Activity Plan for a robot working with children.
The robot facilitates group activities to foster soft skills.

RELIES ON:
{catalog_str}

OUTPUT FORMAT:
You must return a strictly valid JSON object with the following structure:
{{
  "activity_title": "String",
  "target_audience": "String (Grade/Age)",
  "approximate_duration": "String",
  "number_of_students": "String (e.g., '10-15 students')",
  "steps": [
    {{
      "step_type": "canned",
      "robot_script": "Exact words the robot should say."
    }},
    {{
      "step_type": "open",
      "goal": "Description of the interactive goal",
      "suggested_topics": ["Topic 1", "Topic 2"],
      "closing_condition": "Explicit condition for when to move to the next step (e.g., 'After 2-3 students share' or 'When the group agrees on a plan')"
    }},
    ... more steps ...
  ]
}}

INSTRUCTIONS:
1. Break the activity into a linear sequence of steps.
2. Alternate between "canned" (fixed robot speech) and "open" (interactive) steps as needed.
3. "canned": Use for instructions, explanations, transitions, and specific content delivery.
4. "open": Use for discussions, brainstorming, Q&A, or feedback. The robot will dynamically facilitate these.
5. Ensure the flow is logical and covers the entire activity from start to finish.
6. "closing_condition" in open steps is CRITICAL. It defines when the robot should decide to move on.
Ensure the tone is friendly, encouraging, and age-appropriate.
"""

        user_prompt = f"Activity Description: {activity_description}"

        response_text = self.llm_client.get_completion(system_prompt, user_prompt, json_mode=True)
        
        if response_text:
            try:
                plan = json.loads(response_text)
                return plan
            except json.JSONDecodeError:
                print("Error: LLM returned invalid JSON.")
                return None
        return None
