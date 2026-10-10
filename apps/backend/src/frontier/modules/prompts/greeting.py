from pydantic import BaseModel

from frontier.contracts.prompts import Greeting, PromptId
from frontier.modules.prompts.base import Prompt

GREETING_TASK = (
    "Send a short, friendly greeting introducing yourself as Frontier's migration agent. "
    "Do not use any tools."
)


class GreetingPrompt(Prompt):
    id = PromptId.GREETING

    def prompt(self) -> str:
        return GREETING_TASK

    def schema(self) -> type[BaseModel]:
        return Greeting
