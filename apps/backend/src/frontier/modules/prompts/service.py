from frontier.contracts.prompts import GetPromptRequest, RenderedPrompt


class PromptsService:
    """Centralised prompt templates."""

    async def render(self, request: GetPromptRequest) -> RenderedPrompt:
        raise NotImplementedError("prompts.render")
