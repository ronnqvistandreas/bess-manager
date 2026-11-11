"""Behavioral tests for the GitHub Copilot AI Analyst provider."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from copilot.rpc import ToolsListRequest
from copilot.session_events import SessionEventType
from copilot.tools import ToolInvocation
from llm.copilot_provider import CopilotProvider


def _model(
    model_id: str,
    multiplier: float | None,
    prompt_tokens: int | None,
    reasoning_efforts: list[str] | None = None,
):
    return SimpleNamespace(
        id=model_id,
        name=model_id.upper(),
        billing=SimpleNamespace(multiplier=multiplier),
        capabilities=SimpleNamespace(
            limits=SimpleNamespace(
                max_prompt_tokens=prompt_tokens,
                max_context_window_tokens=None,
            ),
        ),
        supported_reasoning_efforts=reasoning_efforts,
        default_reasoning_effort="low" if reasoning_efforts else None,
    )


def test_connection_lists_models_and_selects_zero_multiplier_default(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("COPILOT_CLI_EXTRACT_DIR", "previous-runtime-path")
    models = [
        _model("paid-model", 1.0, 100_000),
        _model("included-model", 0.0, 128_000, ["low", "high"]),
    ]
    client = MagicMock()
    runtime_directory = tmp_path / "runtime"

    async def start_client():
        assert os.environ["COPILOT_CLI_EXTRACT_DIR"] == str(runtime_directory)

    client.start = AsyncMock(side_effect=start_client)
    client.list_models = AsyncMock(return_value=models)
    factory = MagicMock(return_value=client)
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="auto",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=runtime_directory,
        tool_executor=MagicMock(),
        client_factory=factory,
    )

    available_models = asyncio.run(provider.list_models())
    ok, message = asyncio.run(provider.test_connection())

    assert ok is True
    assert "2 models" in message
    assert available_models[1]["billingMultiplier"] == 0.0
    assert available_models[1]["contextWindowTokens"] == 128_000
    assert available_models[1]["reasoningEfforts"] == ["low", "high"]
    assert provider.default_model(available_models) == "included-model"
    client.start.assert_awaited_once()
    factory.assert_called_once()
    assert factory.call_args.kwargs["github_token"] == "github_pat_test"
    assert factory.call_args.kwargs["use_logged_in_user"] is False
    assert factory.call_args.kwargs["mode"] == "empty"
    assert os.environ["COPILOT_CLI_EXTRACT_DIR"] == "previous-runtime-path"


def test_classic_token_is_rejected_without_starting_runtime(tmp_path):
    factory = MagicMock()
    provider = CopilotProvider(
        api_key="ghp_classic_token",
        model="auto",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=MagicMock(),
        client_factory=factory,
    )

    ok, message = asyncio.run(provider.test_connection())

    assert ok is False
    assert "ghp_" in message
    factory.assert_not_called()


def test_context_limit_is_checked_before_session_creation(tmp_path):
    client = MagicMock()
    client.start = AsyncMock()
    client.list_models = AsyncMock(return_value=[_model("small-model", 0.0, 100)])
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="small-model",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=MagicMock(),
        client_factory=MagicMock(return_value=client),
    )

    try:
        asyncio.run(provider.validate_context("x" * 404))
    except ValueError as error:
        assert "prompt limit" in str(error)
    else:
        raise AssertionError("Oversized Copilot context must be rejected.")

    client.create_session.assert_not_called()


def test_auto_context_limit_uses_concrete_model_limits(tmp_path):
    client = MagicMock()
    client.start = AsyncMock()
    client.list_models = AsyncMock(
        return_value=[
            _model("auto", None, None),
            _model("small-model", 0.0, 100),
            _model("large-model", 1.0, 200),
        ]
    )
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="auto",
        reasoning_effort=None,
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=MagicMock(),
        client_factory=MagicMock(return_value=client),
    )

    with pytest.raises(ValueError, match="prompt limit") as error:
        asyncio.run(provider.validate_context("x" * 404))

    assert "100 token limit" in str(error.value)


def test_stream_reply_uses_only_read_only_tools_and_streams_deltas(tmp_path):
    session = MagicMock()
    session.on = MagicMock()
    handler = None

    def subscribe(callback):
        nonlocal handler
        handler = callback
        return MagicMock()

    session.on.side_effect = subscribe

    async def send_and_wait(prompt, timeout):
        assert prompt.startswith("The live system context has been refreshed.")
        tool = next(
            tool
            for tool in client.create_session.call_args.kwargs["tools"]
            if tool.name == "read_file"
        )
        await tool.handler(
            ToolInvocation(
                session_id="chat-1",
                tool_name="read_file",
                arguments={"path": "backend/api.py"},
            )
        )
        handler(
            SimpleNamespace(
                type=SessionEventType.ASSISTANT_MESSAGE_DELTA,
                agent_id=None,
                data=SimpleNamespace(delta_content="Analysis complete."),
            )
        )

    session.send_and_wait = AsyncMock(side_effect=send_and_wait)
    client = MagicMock()
    client.start = AsyncMock()
    client.list_models = AsyncMock(return_value=[])
    client.create_session = AsyncMock(return_value=session)
    executor = MagicMock(return_value="file contents")
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="included-model",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=executor,
        client_factory=MagicMock(return_value=client),
    )

    async def collect():
        return [
            item
            async for item in provider.stream_reply(
                "chat-1",
                "Why did savings change?",
                "analyst system prompt",
                context_update="new live context",
            )
        ]

    events = asyncio.run(collect())
    create_args = client.create_session.call_args.kwargs

    assert [tool.name for tool in create_args["tools"]] == [
        "read_file",
        "search_code",
        "list_files",
    ]
    assert create_args["available_tools"] == []
    assert create_args["system_message"] == {
        "mode": "replace",
        "content": "analyst system prompt",
    }
    assert create_args["reasoning_effort"] is None
    assert (
        "tool_use",
        {
            "tool": "read_file",
            "input": {"path": "backend/api.py"},
        },
    ) in events
    assert ("text_delta", "Analysis complete.") in events
    assert events[-1] == ("turn_complete", None)
    executor.assert_called_once_with("read_file", {"path": "backend/api.py"})


def test_stream_reply_aborts_after_twenty_tool_calls(tmp_path):
    session = MagicMock()
    session.on = MagicMock(return_value=MagicMock())
    session.abort = AsyncMock()
    client = MagicMock()
    client.start = AsyncMock()
    executor = MagicMock(return_value="contents")

    async def send_and_wait(prompt, timeout):
        tool = client.create_session.call_args.kwargs["tools"][0]
        for _ in range(21):
            await tool.handler(
                ToolInvocation(
                    session_id="chat-2",
                    tool_name="read_file",
                    arguments={"path": "backend/api.py"},
                )
            )

    session.send_and_wait = AsyncMock(side_effect=send_and_wait)
    client.create_session = AsyncMock(return_value=session)
    client.list_models = AsyncMock(return_value=[])
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="included-model",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=executor,
        client_factory=MagicMock(return_value=client),
    )

    async def collect():
        return [
            item
            async for item in provider.stream_reply(
                "chat-2", "Explain the schedule", "analyst system prompt"
            )
        ]

    events = asyncio.run(collect())

    assert executor.call_count == 20
    session.abort.assert_awaited_once()
    assert events[-2][0] == "text_delta"
    assert "maximum tool call limit" in events[-2][1]


def test_delete_session_disconnects_and_removes_sdk_history(tmp_path):
    session = MagicMock()
    session.disconnect = AsyncMock()
    client = MagicMock()
    client.delete_session = AsyncMock()
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="auto",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=MagicMock(),
        client_factory=MagicMock(),
    )
    provider._client = client
    provider._sessions["chat-1"] = session

    asyncio.run(provider.delete_session("chat-1"))

    session.disconnect.assert_awaited_once()
    client.delete_session.assert_awaited_once_with("chat-1")
    assert "chat-1" not in provider._sessions


def test_close_deletes_sessions_and_stops_shared_client(tmp_path):
    session = MagicMock()
    session.disconnect = AsyncMock()
    client = MagicMock()
    client.delete_session = AsyncMock()
    client.stop = AsyncMock()
    provider = CopilotProvider(
        api_key="github_pat_test",
        model="auto",
        reasoning_effort="low",
        session_directory=tmp_path / "sessions",
        runtime_directory=tmp_path / "runtime",
        tool_executor=MagicMock(),
        client_factory=MagicMock(),
    )
    provider._client = client
    provider._sessions["chat-1"] = session

    asyncio.run(provider.close())

    session.disconnect.assert_awaited_once()
    client.delete_session.assert_awaited_once_with("chat-1")
    client.stop.assert_awaited_once()
    assert provider._client is None


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("COPILOT_GITHUB_TOKEN"),
    reason="COPILOT_GITHUB_TOKEN is required for the live Copilot SDK check.",
)
def test_live_sdk_exposes_no_builtin_tools(tmp_path):
    async def verify():
        provider = CopilotProvider(
            api_key=os.environ["COPILOT_GITHUB_TOKEN"],
            model="auto",
            reasoning_effort="low",
            session_directory=tmp_path / "sessions",
            runtime_directory=tmp_path / "runtime",
            tool_executor=lambda name, args: "",
        )
        try:
            await provider.list_models()
            session = await provider._get_session(
                "live-tool-allowlist-check",
                "You are a read-only BESS analyst.",
            )
            available = await session.rpc.tools.list(ToolsListRequest(model="auto"))
            assert available.tools == []
        finally:
            await provider.close()

    asyncio.run(verify())
