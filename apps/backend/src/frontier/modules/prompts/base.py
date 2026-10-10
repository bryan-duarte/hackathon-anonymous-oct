from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from frontier.contracts.prompts import PromptId


class Prompt(ABC):
    id: ClassVar[PromptId]

    @abstractmethod
    def prompt(self) -> str: ...

    @abstractmethod
    def schema(self) -> type[BaseModel]: ...
