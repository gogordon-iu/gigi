"""
Azure OpenAI Client for Gigi interaction engine.
"""

import os
import logging
from typing import Optional
from gigi.interaction.llm.client import BaseLLMClient

logger = logging.getLogger(__name__)


class AzureOpenAILLMClient(BaseLLMClient):
    """Client for Azure OpenAI enterprise deployments."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

        self.client = None
        if self.api_key and self.azure_endpoint:
            try:
                from openai import AzureOpenAI

                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    api_version=self.api_version,
                    azure_endpoint=self.azure_endpoint,
                )
            except Exception as e:
                logger.warning(f"Could not initialize Azure OpenAI client: {e}")

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Optional[str]:
        if not self.client:
            logger.error("Azure OpenAI client not initialized. Check API key and endpoint.")
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling Azure OpenAI: {e}")
            return None
