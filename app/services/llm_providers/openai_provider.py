"""
OpenAI LLM provider implementation.
Uses the official OpenAI Python SDK.
"""

from typing import Optional, List, Dict
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (reads from env if not provided)
            model: Model to use (default: gpt-4o)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts on rate limits
        """
        from ...config import OPENAI_API_KEY, LLM_TIMEOUT

        self.api_key = api_key or OPENAI_API_KEY
        self.model = model
        self.timeout = timeout or LLM_TIMEOUT
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment or config")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=float(self.timeout),
            max_retries=self.max_retries,
        )

    async def generate_reply(
        self,
        message: str,
        system_prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mimetype: str = "image/jpeg",
    ) -> str:
        """
        Generate a reply using OpenAI GPT, with optional vision support (gpt-4o).

        When image_url or image_base64 is provided, the message is sent as a
        multimodal content block using the OpenAI Vision API format.

        Args:
            message: The user's message or audio transcription
            system_prompt: System prompt
            context: Previous conversation messages
            max_tokens: Maximum tokens (default: 1024)
            temperature: Sampling temperature
            image_url: Public URL of an image for vision processing
            image_base64: Base64-encoded image (fallback when URL not available)
            image_mimetype: MIME type of the image

        Returns:
            Generated response text
        """
        from ...config import LLM_MAX_TOKENS

        messages = [{"role": "system", "content": system_prompt}]

        if context:
            for msg in context:
                if "role" in msg and "content" in msg:
                    if msg["role"] in ["user", "assistant", "system"]:
                        messages.append({"role": msg["role"], "content": msg["content"]})

        # Build user content — plain text or multimodal (image + text)
        if image_url:
            user_content = [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": message or "What do you see in this image?"},
            ]
        elif image_base64:
            data_url = f"data:{image_mimetype};base64,{image_base64}"
            user_content = [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": message or "What do you see in this image?"},
            ]
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens or LLM_MAX_TOKENS,
                temperature=temperature,
                messages=messages,
            )

            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            else:
                raise ValueError("Empty response from OpenAI API")

        except RateLimitError as e:
            raise Exception(f"OpenAI rate limit exceeded: {str(e)}") from e
        except APITimeoutError as e:
            raise Exception(f"OpenAI API timeout after {self.timeout}s: {str(e)}") from e
        except APIError as e:
            raise Exception(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error calling OpenAI: {str(e)}") from e

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "openai"

    def get_model_name(self) -> str:
        """Return model name"""
        return self.model
