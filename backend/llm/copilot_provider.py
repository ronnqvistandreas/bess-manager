"""GitHub Copilot SDK provider for AI Analyst."""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from copilot import CopilotClient, CopilotSession
from copilot.session_events import SessionEventType
from copilot.tools import Tool, ToolInvocation, ToolResult

from llm.tools import TOOLS

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 20

ToolExecutor = Callable[[str, dict], str]
ClientFactory = Callable[..., CopilotClient]


class CopilotProvider:
    """Copilot agent backend with an SDK-owned tool loop and history."""

    def __init__(
        self,
        api_key: str,
        model: str,
        reasoning_effort: str | None,
        session_directory: Path,
        runtime_directory: Path,
        tool_executor: ToolExecutor,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._session_directory = session_directory
        self._runtime_directory = runtime_directory
        self._tool_executor = tool_executor
        self._client_factory = client_factory or CopilotClient
        self._client: CopilotClient | None = None
        self._models: dict[str, Any] = {}
        self._sessions: dict[str, CopilotSession] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._active_queues: dict[str, asyncio.Queue[tuple[str, Any]]] = {}
        self._turn_states: dict[str, dict[str, Any]] = {}

    async def list_models(self) -> list[dict]:
        """Return model choices and capabilities from the authenticated SDK."""
        client = await self._ensure_client()
        models = await client.list_models()
        self._models = {model.id: model for model in models}
        return [self._serialize_model(model) for model in models]

    async def test_connection(self) -> tuple[bool, str]:
        if self._api_key.startswith("ghp_"):
            return False, "Classic GitHub tokens (ghp_) are not supported."
        try:
            models = await self.list_models()
            return (
                True,
                f"GitHub Copilot connection OK — {len(models)} models available.",
            )
        except Exception:
            logger.exception("GitHub Copilot connection test failed")
            return (
                False,
                "GitHub Copilot connection failed; check the token and access.",
            )

    async def validate_context(self, system_prompt: str) -> None:
        """Fail before a chat begins if the selected model cannot fit its prompt."""
        models = await self.list_models()
        selected = [model for model in models if model["id"] == self._model]
        if self._model == "auto":
            selected = models
        if not selected:
            raise ValueError(f"GitHub Copilot model '{self._model}' is unavailable.")

        limits = [
            model["contextWindowTokens"]
            for model in selected
            if model["contextWindowTokens"] is not None
        ]
        if not limits:
            raise ValueError(
                f"GitHub Copilot did not report a context limit for '{self._model}'."
            )
        if any(model["contextWindowTokens"] is None for model in selected):
            raise ValueError(
                f"GitHub Copilot did not report context limits for all models "
                f"available to '{self._model}'."
            )

        max_prompt_tokens = min(limits)
        estimated_tokens = len(system_prompt) // 4
        if estimated_tokens > max_prompt_tokens:
            raise ValueError(
                "The current system context exceeds the selected Copilot model's "
                f"prompt limit ({estimated_tokens:,} estimated tokens; "
                f"{max_prompt_tokens:,} token limit)."
            )

    async def stream_reply(
        self,
        session_id: str,
        message: str,
        system_prompt: str,
        context_update: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Stream a single reply while the SDK owns conversation and tool state."""
        session = await self._get_session(session_id, system_prompt)
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
            loop = asyncio.get_running_loop()
            self._active_queues[session_id] = queue
            self._turn_states[session_id] = {
                "tool_calls": 0,
                "limit_reached": False,
            }

            def on_event(event: Any) -> None:
                if (
                    event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA
                    and event.agent_id is None
                ):
                    loop.call_soon_threadsafe(
                        queue.put_nowait, ("text_delta", event.data.delta_content)
                    )

            unsubscribe = session.on(on_event)
            prompt = message
            if context_update:
                prompt = (
                    "The live system context has been refreshed. Use this updated "
                    "context for your analysis:\n\n"
                    f"{context_update}\n\nUser question:\n{message}"
                )
            response_task = asyncio.create_task(
                session.send_and_wait(prompt, timeout=300)
            )
            try:
                while not response_task.done():
                    try:
                        event_type, data = await asyncio.wait_for(
                            queue.get(), timeout=0.1
                        )
                    except TimeoutError:
                        continue
                    yield event_type, data

                await response_task
                await asyncio.sleep(0)
                while not queue.empty():
                    yield queue.get_nowait()

                if self._turn_states[session_id]["limit_reached"]:
                    yield (
                        "text_delta",
                        "\n\n*[Reached maximum tool call limit — "
                        "please refine your question.]*",
                    )
                yield "turn_complete", None
            finally:
                unsubscribe()
                self._active_queues.pop(session_id, None)
                self._turn_states.pop(session_id, None)
                if not response_task.done():
                    response_task.cancel()
                    await asyncio.gather(response_task, return_exceptions=True)

    async def delete_session(self, session_id: str) -> None:
        """Delete expired Copilot session history and its local SDK state."""
        self._session_locks.pop(session_id, None)
        self._active_queues.pop(session_id, None)
        self._turn_states.pop(session_id, None)
        session = self._sessions.pop(session_id, None)
        if self._client is not None and session is not None:
            await session.disconnect()
            await self._client.delete_session(session_id)

    async def close(self) -> None:
        """Stop the shared Copilot runtime and discard all temporary sessions."""
        for session_id in list(self._sessions):
            await self.delete_session(session_id)
        if self._client is not None:
            await self._client.stop()
            self._client = None

    async def _ensure_client(self) -> CopilotClient:
        if self._client is None:
            self._session_directory.mkdir(parents=True, exist_ok=True)
            self._runtime_directory.mkdir(parents=True, exist_ok=True)
            env = {
                **os.environ,
                "COPILOT_CLI_EXTRACT_DIR": str(self._runtime_directory),
                "COPILOT_TELEMETRY_DISABLED": "true",
            }
            client = self._client_factory(
                github_token=self._api_key,
                use_logged_in_user=False,
                mode="empty",
                base_directory=str(self._session_directory),
                env=env,
            )
            previous_runtime_directory = os.environ.get("COPILOT_CLI_EXTRACT_DIR")
            os.environ["COPILOT_CLI_EXTRACT_DIR"] = str(self._runtime_directory)
            try:
                await client.start()
            except Exception:
                await client.stop()
                raise
            finally:
                if previous_runtime_directory is None:
                    os.environ.pop("COPILOT_CLI_EXTRACT_DIR", None)
                else:
                    os.environ["COPILOT_CLI_EXTRACT_DIR"] = previous_runtime_directory
            self._client = client
        return self._client

    async def _get_session(self, session_id: str, system_prompt: str) -> CopilotSession:
        session = self._sessions.get(session_id)
        if session is not None:
            return session

        client = await self._ensure_client()
        if not self._models:
            await self.list_models()
        model = self._models.get(self._model)
        reasoning_effort = None
        if (
            model is not None
            and model.supported_reasoning_efforts
            and self._reasoning_effort in model.supported_reasoning_efforts
        ):
            reasoning_effort = self._reasoning_effort
        tools = [
            Tool(
                name=definition["name"],
                description=definition["description"],
                parameters=definition["input_schema"],
                handler=self._tool_handler,
                skip_permission=True,
            )
            for definition in TOOLS
        ]
        session = await client.create_session(
            session_id=session_id,
            model=self._model,
            reasoning_effort=reasoning_effort,
            tools=tools,
            available_tools=[],
            system_message={"mode": "replace", "content": system_prompt},
            streaming=True,
            working_directory=os.getcwd(),
            enable_skills=False,
            enable_session_store=False,
        )
        self._sessions[session_id] = session
        self._session_locks[session_id] = asyncio.Lock()
        return session

    async def _tool_handler(self, invocation: ToolInvocation) -> ToolResult:
        turn_state = self._turn_states[invocation.session_id]
        if turn_state["tool_calls"] >= MAX_TOOL_CALLS:
            turn_state["limit_reached"] = True
            session = self._sessions[invocation.session_id]
            await session.abort()
            return ToolResult(
                text_result_for_llm="Maximum tool call limit reached.",
                result_type="failure",
            )

        turn_state["tool_calls"] += 1
        queue = self._active_queues[invocation.session_id]
        queue.put_nowait(
            (
                "tool_use",
                {
                    "tool": invocation.tool_name,
                    "input": invocation.arguments,
                },
            )
        )
        if not isinstance(invocation.arguments, dict):
            return ToolResult(
                text_result_for_llm="Tool arguments must be an object.",
                result_type="failure",
            )

        result = await asyncio.to_thread(
            self._tool_executor, invocation.tool_name, invocation.arguments
        )
        return ToolResult(text_result_for_llm=result)

    @staticmethod
    def _serialize_model(model: Any) -> dict:
        limits = model.capabilities.limits
        prompt_limit = limits.max_prompt_tokens or limits.max_context_window_tokens
        billing_multiplier = (
            model.billing.multiplier if model.billing is not None else None
        )
        return {
            "id": model.id,
            "name": model.name,
            "billingMultiplier": billing_multiplier,
            "contextWindowTokens": prompt_limit,
            "reasoningEfforts": model.supported_reasoning_efforts or [],
            "defaultReasoningEffort": model.default_reasoning_effort,
        }

    @staticmethod
    def default_model(models: list[dict]) -> str:
        """Prefer a model with no premium-request multiplier, then Auto."""
        for model in models:
            if model["billingMultiplier"] == 0:
                model_id = model["id"]
                if isinstance(model_id, str):
                    return model_id
                raise TypeError("Copilot model metadata has an invalid model ID.")
        return "auto"
