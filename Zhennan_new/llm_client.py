import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")

        if not self.api_key or not self.azure_endpoint:
            raise ValueError("Azure OpenAI API Key and Endpoint must be set in environment variables.")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.azure_endpoint
        )

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """
        Get a completion from the Azure OpenAI model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.7 # Standard for creative but structured tasks
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling Azure OpenAI: {e}")
            return None
