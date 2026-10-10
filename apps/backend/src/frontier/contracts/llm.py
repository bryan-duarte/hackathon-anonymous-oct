from typing import Literal

from pydantic import Field

from frontier.contracts._base import StrictModel


class ChatMessage(StrictModel):
    role: Literal["system", "user", "assistant"]
    content: str


class CompletionRequest(StrictModel):
    messages: list[ChatMessage]
    model: str | None = None
    max_tokens: int = Field(default=4096, gt=0)


class CompletionResponse(StrictModel):
    content: str
    model: str
    input_tokens: int
    output_tokens: int
