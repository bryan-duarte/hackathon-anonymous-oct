from pydantic import JsonValue

from frontier.contracts._base import StrictModel


class ToolSpec(StrictModel):
    name: str
    description: str


class ListToolsRequest(StrictModel):
    pass


class ToolList(StrictModel):
    tools: list[ToolSpec]


class InvokeToolRequest(StrictModel):
    job_id: str
    tool_name: str
    arguments: dict[str, JsonValue]


class ToolResult(StrictModel):
    output: str
    is_error: bool
