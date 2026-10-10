from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from frontier.clients.secrets import SecretsClient
from frontier.core.logging_config import get_logger
from frontier.modules.tools.redaction import redact_for_run

logger = get_logger(__name__)


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
