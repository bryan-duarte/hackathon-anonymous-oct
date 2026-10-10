from frontier.contracts._base import StrictModel


class GetPromptRequest(StrictModel):
    name: str
    variables: dict[str, str] = {}


class RenderedPrompt(StrictModel):
    name: str
    text: str
