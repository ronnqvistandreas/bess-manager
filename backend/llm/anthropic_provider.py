"""Anthropic Claude provider for AI Analyst."""

import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from llm.protocol import ToolCall, TurnResult
from llm.tools import TOOLS

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Streaming Claude API backend with tool use."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def stream_turn(
        self,
        messages: list[dict],
        system_prompt: Any,
    ) -> AsyncIterator[tuple[str, Any]]:
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        text_so_far = ""

        async with client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            async for event in stream:
                if hasattr(event, "type") and event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        text_so_far += event.delta.text
                        yield ("text_delta", event.delta.text)

            response = await stream.get_final_message()

        tool_calls = []
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        yield (
            "turn_complete",
            TurnResult(
                text=text_so_far,
                tool_calls=tool_calls,
                assistant_content=assistant_content,
            ),
        )

    async def test_connection(self) -> tuple[bool, str]:
        try:
            client = anthropic.AsyncAnthropic(api_key=self._api_key)
            await client.messages.create(
                model=self._model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True, f"Claude connection OK — model: {self._model}"
        except anthropic.AuthenticationError:
            return False, "Invalid Anthropic API key."
        except anthropic.APIError as e:
            logger.error("Anthropic test connection error: %s", e)
            return False, f"Claude API error: {e.message}"
        except Exception as e:
            logger.exception("Anthropic test connection failed: %s", e)
            return False, "Could not connect to Claude API."
