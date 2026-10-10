from typing import TYPE_CHECKING

from frontier.contracts.prompts import GetPromptRequest, RenderedPrompt

if TYPE_CHECKING:
    from frontier.modules.prompts import PromptsService


class PromptsClient:
    def __init__(self, service: "PromptsService") -> None:
        self._service = service

    async def render(self, request: GetPromptRequest) -> RenderedPrompt:
        return await self._service.render(request)
