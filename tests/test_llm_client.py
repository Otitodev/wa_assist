"""
Tests for the LLM provider factory and context passing.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_client import get_llm_provider, UnsupportedProviderError
from app.services.llm_providers.anthropic_provider import AnthropicProvider
from app.services.llm_providers.openai_provider import OpenAIProvider


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------

def test_get_llm_provider_anthropic():
    provider = get_llm_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)


def test_get_llm_provider_openai():
    provider = get_llm_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_get_llm_provider_case_insensitive():
    assert isinstance(get_llm_provider("Anthropic"), AnthropicProvider)
    assert isinstance(get_llm_provider("OPENAI"), OpenAIProvider)


def test_get_llm_provider_unsupported_raises():
    with pytest.raises(UnsupportedProviderError):
        get_llm_provider("nonexistent_provider")


# ---------------------------------------------------------------------------
# Anthropic provider — context passing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_passes_context_as_messages():
    """Context list is converted to Anthropic messages format."""
    provider = AnthropicProvider()

    context = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ]

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="AI reply")]

    with patch.object(provider, "client") as mockclient:
        mockclient.messages.create = AsyncMock(return_value=mock_message)
        reply = await provider.generate_reply(
            message="What's 2+2?",
            system_prompt="You are helpful.",
            context=context,
        )

    call_kwargs = mockclient.messages.create.call_args.kwargs
    messages_sent = call_kwargs["messages"]
    # Context messages should appear before the current user message
    assert messages_sent[0]["role"] == "user"
    assert messages_sent[0]["content"] == "Hello"
    assert messages_sent[1]["role"] == "assistant"
    assert messages_sent[-1]["role"] == "user"
    assert reply == "AI reply"


@pytest.mark.asyncio
async def test_anthropic_no_context():
    """Works correctly when context is None or empty."""
    provider = AnthropicProvider()

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Response")]

    with patch.object(provider, "client") as mockclient:
        mockclient.messages.create = AsyncMock(return_value=mock_message)
        reply = await provider.generate_reply(
            message="Hello",
            system_prompt="Be helpful.",
        )

    call_kwargs = mockclient.messages.create.call_args.kwargs
    assert call_kwargs["messages"][-1]["content"] == "Hello"
    assert reply == "Response"


# ---------------------------------------------------------------------------
# OpenAI provider — context passing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_passes_context_as_messages():
    """Context is prepended to OpenAI chat messages."""
    provider = OpenAIProvider()

    context = [
        {"role": "user", "content": "What's your name?"},
        {"role": "assistant", "content": "I'm Whaply AI."},
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "4"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(provider, "client") as mockclient:
        mockclient.chat.completions.create = AsyncMock(return_value=mock_completion)
        reply = await provider.generate_reply(
            message="What's 2+2?",
            system_prompt="You are helpful.",
            context=context,
        )

    call_kwargs = mockclient.chat.completions.create.call_args.kwargs
    messages_sent = call_kwargs["messages"]
    # system, context[0], context[1], user message
    assert messages_sent[0]["role"] == "system"
    assert messages_sent[1]["role"] == "user"
    assert messages_sent[2]["role"] == "assistant"
    assert messages_sent[-1]["role"] == "user"
    assert reply == "4"
