from pydantic import JsonValue

from frontier.contracts._base import StrictModel


class CallMcpToolRequest(StrictModel):
    server: str
    tool: str
    arguments: dict[str, JsonValue]


class McpToolResult(StrictModel):
    content: str
    is_error: bool
