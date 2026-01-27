"""
LLM Client Factory.
Returns the appropriate LLM provider based on configuration.
"""

from typing import Optional
from .llm_providers.base import BaseLLMProvider
from .llm_providers.anthropic_provider import AnthropicProvider
from .llm_providers.openai_provider import OpenAIProvider


class UnsupportedProviderError(Exception):
    """Raised when an unsupported LLM provider is requested"""
    pass


def get_llm_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> BaseLLMProvider:
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: Provider name ("anthropic", "openai").
                      If None, uses LLM_PROVIDER from config.
        model: Model name to use. If None, uses provider's default.
        **kwargs: Additional arguments passed to provider constructor
                 (e.g., api_key, timeout, max_retries)

    Returns:
        Initialized LLM provider instance

    Raises:
        UnsupportedProviderError: If provider_name is not supported
        ValueError: If required API keys are missing

    Example:
        >>> provider = get_llm_provider("anthropic")
        >>> reply = await provider.generate_reply("Hello", "You are helpful")
    """
    from ..config import LLM_PROVIDER

    # Use config default if not specified
    provider = (provider_name or LLM_PROVIDER).lower().strip()

    if provider == "anthropic":
        provider_kwargs = {}
        if model:
            provider_kwargs["model"] = model
        provider_kwargs.update(kwargs)
        return AnthropicProvider(**provider_kwargs)

    elif provider == "openai":
        provider_kwargs = {}
        if model:
            provider_kwargs["model"] = model
        provider_kwargs.update(kwargs)
        return OpenAIProvider(**provider_kwargs)

    else:
        raise UnsupportedProviderError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported providers: anthropic, openai"
        )


async def generate_ai_reply(
    message: str,
    system_prompt: str,
    provider_name: Optional[str] = None,
    context: Optional[list] = None,
    **kwargs
) -> str:
    """
    Convenience function to generate an AI reply using the configured provider.

    Args:
        message: User message to respond to
        system_prompt: System prompt defining assistant behavior
        provider_name: LLM provider to use (default: from config)
        context: Previous conversation messages
        **kwargs: Additional arguments for generate_reply

    Returns:
        Generated reply text

    Example:
        >>> reply = await generate_ai_reply(
        ...     "What is WhatsApp?",
        ...     "You are a helpful assistant"
        ... )
    """
    provider = get_llm_provider(provider_name)
    return await provider.generate_reply(
        message=message,
        system_prompt=system_prompt,
        context=context,
        **kwargs
    )
