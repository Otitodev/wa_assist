"""
Base abstract class for LLM providers.
All LLM providers must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate_reply(
        self,
        message: str,
        system_prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate a reply using the LLM.

        Args:
            message: The user's message to respond to
            system_prompt: System prompt defining the assistant's behavior
            context: Optional list of previous messages for conversation context
                     Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            max_tokens: Maximum tokens in the response (uses provider default if not specified)
            temperature: Sampling temperature (0.0-1.0, higher = more creative)

        Returns:
            Generated response text

        Raises:
            Exception: If the LLM API call fails
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Return the name of this provider (e.g., "anthropic", "openai").

        Returns:
            Provider name string
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Return the model being used (e.g., "claude-3-5-sonnet-20241022").

        Returns:
            Model name string
        """
        pass
