from frontier.contracts.tools import InvokeToolRequest, ListToolsRequest, ToolList, ToolResult


class ToolsService:
    """Internal tools for agents and subagents."""

    async def list_tools(self, request: ListToolsRequest) -> ToolList:
        raise NotImplementedError("tools.list_tools")

    async def invoke(self, request: InvokeToolRequest) -> ToolResult:
        raise NotImplementedError("tools.invoke")
