from frontier.contracts.mcp import CallMcpToolRequest, McpToolResult


class McpGatewayService:
    """Consumption of external MCP servers."""

    async def call_tool(self, request: CallMcpToolRequest) -> McpToolResult:
        raise NotImplementedError("mcp_gateway.call_tool")
