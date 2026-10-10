from pydantic import BaseModel

from frontier.contracts.prompts import PromptId
from frontier.modules.prompts.base import Prompt
from frontier.modules.prompts.errors import DuplicatePromptIdError, MissingPromptsError
from frontier.modules.prompts.greeting import GreetingPrompt
from frontier.modules.prompts.migration_agent import MigrationAgentPrompt

PROMPTS: tuple[Prompt, ...] = (MigrationAgentPrompt(), GreetingPrompt())


class PromptsService:
    """Centralised prompt catalogue."""

    def __init__(self, prompts: tuple[Prompt, ...] = PROMPTS) -> None:
        self._prompts = _index_by_id(prompts)

    def get_text(self, prompt_id: PromptId) -> str:
        return self._prompts[prompt_id].prompt()

    def get_schema(self, prompt_id: PromptId) -> type[BaseModel]:
        return self._prompts[prompt_id].schema()


def _index_by_id(prompts: tuple[Prompt, ...]) -> dict[PromptId, Prompt]:
    prompts_by_id: dict[PromptId, Prompt] = {}
    for prompt in prompts:
        if prompt.id in prompts_by_id:
            raise DuplicatePromptIdError(prompt.id)
        prompts_by_id[prompt.id] = prompt

    missing_ids = set(PromptId) - prompts_by_id.keys()
    if missing_ids:
        raise MissingPromptsError(missing_ids)
    return prompts_by_id
