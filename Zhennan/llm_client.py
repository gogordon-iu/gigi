import os
import json
import requests
#from dotenv import load_dotenv

# Load environment variables
#load_dotenv()

class LLMClient:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.deployment_name = os.getenv("OLLAMA_MODEL", "hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M")

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """
        Get a completion from the Ollama model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        payload = {
            "model": self.deployment_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.7
            }
        }

        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return None