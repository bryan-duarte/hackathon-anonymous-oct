from typing import TYPE_CHECKING

from frontier.contracts.sessions import (
    AppendMessageRequest,
    GetHistoryRequest,
    SessionHistory,
    SessionMessage,
)

if TYPE_CHECKING:
    from frontier.modules.sessions import SessionsService


class SessionsClient:
    def __init__(self, service: "SessionsService") -> None:
        self._service = service

    async def append_message(self, request: AppendMessageRequest) -> SessionMessage:
        return await self._service.append_message(request)

    async def get_history(self, request: GetHistoryRequest) -> SessionHistory:
        return await self._service.get_history(request)
