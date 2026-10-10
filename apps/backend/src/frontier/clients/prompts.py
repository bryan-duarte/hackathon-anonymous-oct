from typing import TYPE_CHECKING

from pydantic import BaseModel

from frontier.contracts.prompts import PromptId

if TYPE_CHECKING:
    from frontier.modules.prompts import PromptsService


class PromptsClient:
    def __init__(self, service: "PromptsService") -> None:
        self._service = service

    def get_text(self, prompt_id: PromptId) -> str:
        return self._service.get_text(prompt_id)

    def get_schema(self, prompt_id: PromptId) -> type[BaseModel]:
        return self._service.get_schema(prompt_id)
