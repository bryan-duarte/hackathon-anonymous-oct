from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel

if TYPE_CHECKING:
    from frontier.modules.llm_gateway import LlmGatewayService


class LlmClient:
    def __init__(self, service: "LlmGatewayService") -> None:
        self._service = service

    def chat_model(self) -> BaseChatModel:
        return self._service.chat_model()
