"""
Anthropic Claude LLM provider implementation.
Uses the official Anthropic Python SDK.
"""

import os
from typing import Optional, List, Dict
from anthropic import AsyncAnthropic, APIError, RateLimitError, APITimeoutError
from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (reads from env if not provided)
            model: Model to use (default: claude-3-5-sonnet-20241022)
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts on rate limits
        """
        from ...config import ANTHROPIC_API_KEY, LLM_TIMEOUT

        self.api_key = api_key or ANTHROPIC_API_KEY
        self.model = model
        self.timeout = timeout or LLM_TIMEOUT
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment or config")

        self.client = AsyncAnthropic(
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
        Generate a reply using Claude, with optional vision support.

        When image_url or image_base64 is provided, the user message is sent
        as a multimodal content block (image + text) using the Anthropic Vision API.

        Args:
            message: The user's message or audio transcription
            system_prompt: System prompt
            context: Previous conversation messages
            max_tokens: Maximum tokens (default: 1024)
            temperature: Sampling temperature
            image_url: Public URL of an image for Claude Vision
            image_base64: Base64-encoded image (used if image_url not provided)
            image_mimetype: MIME type of the image

        Returns:
            Generated response text
        """
        from ...config import LLM_MAX_TOKENS

        # Build messages array
        messages = []

        # Add context if provided
        if context:
            for msg in context:
                if "role" in msg and "content" in msg:
                    if msg["role"] in ["user", "assistant"]:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

        # Build user content — plain text or multimodal (image + text)
        if image_url or image_base64:
            # Vision: build image block
            if image_url:
                image_block = {
                    "type": "image",
                    "source": {"type": "url", "url": image_url},
                }
            else:
                image_block = {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_mimetype,
                        "data": image_base64,
                    },
                }
            user_content = [
                image_block,
                {"type": "text", "text": message or "What do you see in this image?"},
            ]
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        # Ensure messages start with user
        while messages and messages[0]["role"] == "assistant":
            messages.pop(0)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or LLM_MAX_TOKENS,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
            )

            if response.content and len(response.content) > 0:
                return response.content[0].text
            else:
                raise ValueError("Empty response from Claude API")

        except RateLimitError as e:
            raise Exception(f"Anthropic rate limit exceeded: {str(e)}") from e
        except APITimeoutError as e:
            raise Exception(f"Anthropic API timeout after {self.timeout}s: {str(e)}") from e
        except APIError as e:
            raise Exception(f"Anthropic API error: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error calling Claude: {str(e)}") from e

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "anthropic"

    def get_model_name(self) -> str:
        """Return model name"""
        return self.model
