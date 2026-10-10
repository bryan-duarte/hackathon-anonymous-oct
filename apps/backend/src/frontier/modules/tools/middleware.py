from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, AnyMessage, ToolCall, ToolMessage
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from frontier.clients.secrets import SecretsClient
from frontier.core.logging_config import get_logger
from frontier.modules.tools.redaction import redact_for_run

logger = get_logger(__name__)

MESSAGES_KEY = "messages"
PLANNING_TOOL = "write_todos"
REPEATED_CALL_LIMIT = 3
REPEATED_PLANNING_LIMIT = 3
LOOP_REFUSAL = (
    "loop_detected: you already called {tool} several times in a row without doing anything "
    "else, so this call was not executed. Do the next unfinished step of your task with a "
    "different tool, or, if your work is done, call your final summary tool now."
)


class ToolOutputGuardMiddleware(AgentMiddleware):
    """Redacts tool results and turns tool failures into readable errors, not aborted runs."""

    def __init__(self, *, secrets: SecretsClient) -> None:
        super().__init__()
        self._secrets = secrets

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        context = request.runtime.context
        tool_name = request.tool_call["name"]
        try:
            tool_result = await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as error:
            logger.exception("migration_tool_failed", tool=tool_name)
            failure_message = await redact_for_run(
                self._secrets, f"tool_failed: {type(error).__name__}: {error}", context
            )
            return ToolMessage(
                content=failure_message,
                tool_call_id=request.tool_call["id"],
                name=tool_name,
                status="error",
            )

        has_text_content = isinstance(tool_result, ToolMessage) and isinstance(
            tool_result.content, str
        )
        if not has_text_content:
            return tool_result
        redacted_content = await redact_for_run(self._secrets, tool_result.content, context)
        return tool_result.model_copy(update={"content": redacted_content})


class RepeatedCallGuardMiddleware(AgentMiddleware):
    """Stops degenerate loops: refuses a tool call the agent keeps repeating without progress."""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        tool_call = request.tool_call
        previous_calls = _previous_tool_calls(request.state.get(MESSAGES_KEY, []), tool_call["id"])
        is_looping = _streak(previous_calls, _same_call(tool_call)) >= REPEATED_CALL_LIMIT or (
            tool_call["name"] == PLANNING_TOOL
            and _streak(previous_calls, _planning_call) >= REPEATED_PLANNING_LIMIT
        )
        if not is_looping:
            return await handler(request)

        logger.warning("migration_tool_loop_refused", tool=tool_call["name"])
        return ToolMessage(
            content=LOOP_REFUSAL.format(tool=tool_call["name"]),
            tool_call_id=tool_call["id"],
            name=tool_call["name"],
            status="error",
        )


def _previous_tool_calls(messages: list[AnyMessage], current_call_id: str) -> list[ToolCall]:
    return [
        call
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["id"] != current_call_id
    ]


def _streak(previous_calls: list[ToolCall], matches: Callable[[ToolCall], bool]) -> int:
    streak = 0
    for call in reversed(previous_calls):
        if not matches(call):
            break
        streak += 1
    return streak


def _same_call(tool_call: ToolCall) -> Callable[[ToolCall], bool]:
    return partial(_is_identical_call, tool_call)


def _is_identical_call(reference: ToolCall, candidate: ToolCall) -> bool:
    return candidate["name"] == reference["name"] and candidate["args"] == reference["args"]


def _planning_call(candidate: ToolCall) -> bool:
    return candidate["name"] == PLANNING_TOOL
