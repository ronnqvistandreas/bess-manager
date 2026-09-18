"""Google Gemini provider for AI Analyst."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from llm.protocol import ToolCall, TurnResult
from llm.tools import TOOLS

logger = logging.getLogger(__name__)


def _anthropic_tools_to_gemini() -> list[types.Tool]:
    """Convert shared tool definitions to Gemini function declarations."""
    declarations = []
    for tool in TOOLS:
        declarations.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters_json_schema=tool["input_schema"],
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _messages_to_gemini_contents(messages: list[dict]) -> list[types.Content]:
    """Convert Anthropic-style message history to Gemini Content objects."""
    contents: list[types.Content] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if role == "user" and isinstance(content, str):
            contents.append(
                types.Content(role="user", parts=[types.Part(text=content)])
            )
        elif role == "assistant" and isinstance(content, str):
            contents.append(
                types.Content(role="model", parts=[types.Part(text=content)])
            )
        elif role == "assistant" and isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "text":
                    parts.append(types.Part(text=block.get("text", "")))
                elif block.get("type") == "tool_use":
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=block["name"],
                                args=block.get("input", {}),
                            )
                        )
                    )
            if parts:
                contents.append(types.Content(role="model", parts=parts))
        elif role == "user" and isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "tool_result":
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=block.get("name", "unknown_tool"),
                                response={"result": block.get("content", "")},
                            )
                        )
                    )
            if parts:
                contents.append(types.Content(role="user", parts=parts))

    return contents


def _system_prompt_to_text(system_prompt: Any) -> str:
    """Flatten system prompt blocks to a single string for Gemini."""
    if isinstance(system_prompt, str):
        return system_prompt
    if isinstance(system_prompt, list):
        return "\n\n".join(
            block.get("text", "") for block in system_prompt if isinstance(block, dict)
        )
    return str(system_prompt)


class GoogleProvider:
    """Streaming Google Gemini API backend with function calling."""

    def __init__(
        self, api_key: str, model: str, thinking_level: str = "low"
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._thinking_level = thinking_level
        self._client = genai.Client(api_key=api_key)

    def _build_config(self, system_text: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system_text,
            tools=_anthropic_tools_to_gemini(),
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking_level),
        )

    async def stream_turn(
        self,
        messages: list[dict],
        system_prompt: Any,
    ) -> AsyncIterator[tuple[str, Any]]:
        system_text = _system_prompt_to_text(system_prompt)
        contents = _messages_to_gemini_contents(messages)
        config = self._build_config(system_text)

        text_so_far = ""
        tool_calls: list[ToolCall] = []
        assistant_content: list[dict] = []

        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                text_so_far += chunk.text
                yield ("text_delta", chunk.text)

            for fc in chunk.function_calls or []:
                if not fc.name:
                    continue
                call_id = fc.id or str(uuid.uuid4())
                args = dict(fc.args) if fc.args else {}
                tool_calls.append(ToolCall(id=call_id, name=fc.name, input=args))
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": fc.name,
                        "input": args,
                    }
                )

        if text_so_far:
            assistant_content.insert(0, {"type": "text", "text": text_so_far})

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
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents="Hi",
                config=types.GenerateContentConfig(
                    max_output_tokens=5,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=self._thinking_level
                    ),
                ),
            )
            if response.text:
                return True, f"Gemini connection OK — model: {self._model}"
            return True, f"Gemini connection OK — model: {self._model}"
        except Exception as e:
            error_msg = str(e)
            if "API key" in error_msg or "401" in error_msg or "403" in error_msg:
                return False, "Invalid Google API key."
            logger.error("Google test connection error: %s", e)
            return False, f"Gemini API error: {error_msg}"
