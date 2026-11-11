"""Factory for AI Analyst LLM providers."""

from collections.abc import Callable
from pathlib import Path

from llm.anthropic_provider import AnthropicProvider
from llm.copilot_provider import CopilotProvider
from llm.google_provider import GoogleProvider
from llm.protocol import LLMProvider, ReplyLLMProvider

Provider = LLMProvider | ReplyLLMProvider


def get_provider(
    provider_name: str,
    api_key: str,
    model: str,
    thinking_level: str | None = None,
    reasoning_effort: str | None = None,
    session_directory: Path | None = None,
    runtime_directory: Path | None = None,
    tool_executor: Callable[[str, dict], str] | None = None,
) -> Provider:
    """Return an LLM provider instance for the given configuration."""
    if provider_name == "google":
        return GoogleProvider(
            api_key=api_key,
            model=model,
            thinking_level=thinking_level or "low",
        )
    if provider_name == "copilot":
        if (
            session_directory is None
            or runtime_directory is None
            or tool_executor is None
        ):
            raise ValueError("Copilot provider requires session and runtime paths.")
        return CopilotProvider(
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            session_directory=session_directory,
            runtime_directory=runtime_directory,
            tool_executor=tool_executor,
        )
    return AnthropicProvider(api_key=api_key, model=model)
