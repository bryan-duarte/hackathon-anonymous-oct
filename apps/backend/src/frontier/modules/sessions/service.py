from frontier.contracts.sessions import (
    AppendMessageRequest,
    GetHistoryRequest,
    SessionHistory,
    SessionMessage,
)


class SessionsService:
    """Conversation history of an agent session."""

    async def append_message(self, request: AppendMessageRequest) -> SessionMessage:
        raise NotImplementedError("sessions.append_message")

    async def get_history(self, request: GetHistoryRequest) -> SessionHistory:
        raise NotImplementedError("sessions.get_history")
