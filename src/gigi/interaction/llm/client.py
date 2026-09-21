"""
LLM Client abstractions for Gigi interaction engine.
Supports Ollama (local), OpenAI API, and RKLLM server.
"""

import os
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)


class BaseLLMClient:
    """Base interface for interaction LLM providers."""

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Optional[str]:
        raise NotImplementedError


class OllamaLLMClient(BaseLLMClient):
    """Client for local Ollama models (e.g. Qwen 0.5B / 1.5B / 7B)."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling Ollama at {self.base_url}: {e}")
            return None


class OpenAILLMClient(BaseLLMClient):
    """Client for standard OpenAI chat completions API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("openai package not installed.")

    def get_completion(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Optional[str]:
        if not self.client:
            logger.error("OpenAI client not configured or missing API key.")
            return None

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None


# Default LLMClient alias
LLMClient = OllamaLLMClient
