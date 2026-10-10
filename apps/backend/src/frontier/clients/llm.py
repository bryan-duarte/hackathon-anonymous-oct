from typing import TYPE_CHECKING

from frontier.contracts.llm import CompletionRequest, CompletionResponse

if TYPE_CHECKING:
    from frontier.modules.llm_gateway import LlmGatewayService


class LlmClient:
    def __init__(self, service: "LlmGatewayService") -> None:
        self._service = service

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return await self._service.complete(request)
