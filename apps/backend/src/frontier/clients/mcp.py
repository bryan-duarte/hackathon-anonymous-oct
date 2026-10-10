from typing import TYPE_CHECKING

from frontier.contracts.mcp import CallMcpToolRequest, McpToolResult

if TYPE_CHECKING:
    from frontier.modules.mcp_gateway import McpGatewayService


class McpClient:
    def __init__(self, service: "McpGatewayService") -> None:
        self._service = service

    async def call_tool(self, request: CallMcpToolRequest) -> McpToolResult:
        return await self._service.call_tool(request)
