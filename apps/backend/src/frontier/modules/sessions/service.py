from collections.abc import Sequence
from uuid import uuid4

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from frontier.contracts.sessions import Role, SessionHistory, SessionMessage

ROLE_BY_MESSAGE_TYPE: dict[str, Role] = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
    "tool": "tool",
}


class SessionsService:
    """Conversation history of an agent session, persisted by the LangGraph checkpointer."""

    def __init__(self, checkpointer: BaseCheckpointSaver) -> None:
        self._checkpointer = checkpointer

    def checkpointer(self) -> BaseCheckpointSaver:
        return self._checkpointer

    def new_session_id(self) -> str:
        return uuid4().hex

    def build_history(
        self, session_id: str, messages: Sequence[BaseMessage], limit: int
    ) -> SessionHistory:
        return SessionHistory(
            session_id=session_id,
            messages=[
                SessionMessage(role=ROLE_BY_MESSAGE_TYPE[message.type], content=message.text)
                for message in messages[-limit:]
                if message.type in ROLE_BY_MESSAGE_TYPE
            ],
        )
