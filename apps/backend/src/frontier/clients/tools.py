from typing import TYPE_CHECKING

from frontier.contracts.tools import InvokeToolRequest, ListToolsRequest, ToolList, ToolResult

if TYPE_CHECKING:
    from frontier.modules.tools import ToolsService


class ToolsClient:
    def __init__(self, service: "ToolsService") -> None:
        self._service = service

    async def list_tools(self, request: ListToolsRequest) -> ToolList:
        return await self._service.list_tools(request)

    async def invoke(self, request: InvokeToolRequest) -> ToolResult:
        return await self._service.invoke(request)
