"""LLM provider protocol for AI Analyst."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    input: dict


@dataclass
class TurnResult:
    """Result of one model turn (may include tool calls)."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_content: list[dict] = field(default_factory=list)


class LLMProvider(Protocol):
    """Async streaming LLM with tool-use support."""

    async def stream_turn(
        self,
        messages: list[dict],
        system_prompt: Any,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Stream one model turn.

        Yields:
            ('text_delta', str) for incremental text.
            ('turn_complete', TurnResult) when the turn finishes.
        """
        ...

    async def test_connection(self) -> tuple[bool, str]:
        """Perform a minimal live API call. Returns (ok, message)."""
        ...
