"""Tests for Google Gemini LLM provider."""

import asyncio
import base64
from unittest.mock import MagicMock

from google.genai import types

from llm.google_provider import GoogleProvider, _messages_to_gemini_contents
from llm.protocol import TurnResult


class TestMessagesToGeminiContents:
    def test_tool_use_round_trip_preserves_thought_signature(self):
        signature_b64 = base64.b64encode(b"gemini-thought-sig").decode()
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "get_status",
                        "input": {"detail": "full"},
                        "thought_signature": signature_b64,
                    }
                ],
            }
        ]

        contents = _messages_to_gemini_contents(messages)

        assert len(contents) == 1
        part = contents[0].parts[0]
        assert part.function_call.name == "get_status"
        assert part.function_call.args == {"detail": "full"}
        assert part.thought_signature == b"gemini-thought-sig"


class TestGoogleProviderStreamTurn:
    def _collect(self, async_gen):
        return asyncio.run(self._alist(async_gen))

    @staticmethod
    async def _alist(gen):
        items = []
        async for item in gen:
            items.append(item)
        return items

    def test_stream_turn_captures_thought_signature_from_chunks(self):
        signature_b64 = base64.b64encode(b"stream-thought-sig").decode()
        function_call = types.FunctionCall(
            id="call-42",
            name="search_docs",
            args={"query": "battery"},
        )
        part = types.Part(
            function_call=function_call,
            thought_signature=signature_b64,
        )
        chunk = types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(role="model", parts=[part]),
                )
            ]
        )

        async def fake_stream(*args, **kwargs):
            async def _iter():
                yield chunk

            return _iter()

        provider = GoogleProvider("AIza-test", "gemini-3-flash-preview")
        mock_models = MagicMock()
        mock_models.generate_content_stream = fake_stream
        provider._client = MagicMock()
        provider._client.aio.models = mock_models

        events = self._collect(
            provider.stream_turn([{"role": "user", "content": "search"}], "system")
        )

        assert events[-1][0] == "turn_complete"
        result = events[-1][1]
        assert isinstance(result, TurnResult)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search_docs"
        assert result.assistant_content == [
            {
                "type": "tool_use",
                "id": "call-42",
                "name": "search_docs",
                "input": {"query": "battery"},
                "thought_signature": signature_b64,
            }
        ]

        contents = _messages_to_gemini_contents(
            [{"role": "assistant", "content": result.assistant_content}]
        )
        restored_part = contents[0].parts[0]
        assert restored_part.thought_signature == b"stream-thought-sig"
