from frontier.contracts.llm import CompletionRequest, CompletionResponse


class LlmGatewayService:
    """Unified access to LLM providers."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError("llm_gateway.complete")
