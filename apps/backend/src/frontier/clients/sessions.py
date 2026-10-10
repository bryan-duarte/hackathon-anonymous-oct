from collections.abc import Sequence
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from frontier.contracts.sessions import SessionHistory

if TYPE_CHECKING:
    from frontier.modules.sessions import SessionsService


class SessionsClient:
    def __init__(self, service: "SessionsService") -> None:
        self._service = service

    def checkpointer(self) -> BaseCheckpointSaver:
        return self._service.checkpointer()

    def new_session_id(self) -> str:
        return self._service.new_session_id()

    def build_history(
        self, session_id: str, messages: Sequence[BaseMessage], limit: int
    ) -> SessionHistory:
        return self._service.build_history(session_id, messages, limit)
