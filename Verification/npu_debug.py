import requests
import json
import time

# URL for the RKLLM server (from conversation.py)
url = "http://localhost:8080/rkllm_chat"

# System content provided by the user
system_content = """You are Gigi, a friendly educational robot talking to a child.
CURRENT STEP: {
  "closing_condition": "After the student shares at least two basic needs.",
  "goal": "Encourage the student to brainstorm what humans need to survive anywhere, especially on another planet.",
  "step_type": "open",
  "suggested_topics": [
    "Food and water",
    "Air",
    "Shelter",
    "Clothing",
    "Fun activities"
  ]
}

YOUR ROLE:
1. Analyze the student's input in the context of the current step.
2. If the "closing_condition" is met, output exactly: [NEXT_STEP]
3. Otherwise, keep the conversation flowing naturally towards the goal.

MANDATORY OUTPUT RULES:
- Reply with ONLY ONE or TWO short spoken sentences.
- DO NOT use lists, bullet points, or numbering.
- DO NOT give multiple points or long explanations.
- Speak naturally like you are talking out loud.
- Include non-verbal actions in square brackets (e.g., [nod], [wave hands]).
- Stop immediately after the first or second sentence.
"""

# User content with the specific student input that caused issues
user_content = """Recent Interaction History:
robot: Hello, explorers! Today, we’re going to imagine what it would be like to live on Mars. Our mission is to design the perfect habitat for humans to survive and thrive on the Red Planet. Are you ready? [smile] Please tell me some basic needs to survive on Mars!
student: We would need water.

Generate Robot Response:"""

payload = {
    "model": "qwen",
    "messages": [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ],
    "stream": False
}

def test_npu():
    print("--- NPU DEBUG TEST ---")
    print(f"URL: {url}")
    print(f"Student Input: \"We wouldn't... need water. Doctor. wouldn't need water.\"")
    print("-" * 30)

    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)
        duration = time.time() - start_time
        
        response.raise_for_status()
        result = response.json()
        
        print(f"Time taken: {duration:.2f}s")
        
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            print("\nLLM Output (Raw):")
            print(content)
            
            # Simulated truncation from conversation.py
            import re
            def clean_response(text):
                text = re.sub(r"^(robot:|assistant:|student:|gigi:)\s*", "", text.strip(), flags=re.IGNORECASE)
                text = re.split(r"\n\s*(student:|robot:|user:|assistant:|gigi:)", text, flags=re.IGNORECASE)[0]
                return text.strip()
            
            cleaned = clean_response(content)
            print("\nLLM Output (Cleaned):")
            print(cleaned)
        else:
            print("\nNo choices returned in response.")
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        print(f"\nError calling NPU server: {e}")

if __name__ == "__main__":
    test_npu()
