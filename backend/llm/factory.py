"""Factory for AI Analyst LLM providers."""

from llm.anthropic_provider import AnthropicProvider
from llm.google_provider import GoogleProvider
from llm.protocol import LLMProvider


def get_provider(
    provider_name: str,
    api_key: str,
    model: str,
    thinking_level: str | None = None,
) -> LLMProvider:
    """Return an LLM provider instance for the given configuration."""
    if provider_name == "google":
        return GoogleProvider(
            api_key=api_key,
            model=model,
            thinking_level=thinking_level or "low",
        )
    return AnthropicProvider(api_key=api_key, model=model)
