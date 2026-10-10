from typing import TYPE_CHECKING

from frontier.contracts.guardrails import GuardrailRejection
from frontier.contracts.orchestrator import (
    ChatReply,
    ChatRequest,
    RunMigrationRequest,
    RunMigrationResult,
)
from frontier.contracts.prompts import Greeting
from frontier.contracts.sessions import GetHistoryRequest, SessionHistory

if TYPE_CHECKING:
    from frontier.modules.orchestrator import OrchestratorService


class OrchestratorClient:
    def __init__(self, service: "OrchestratorService") -> None:
        self._service = service

    async def greet(self) -> Greeting:
        return await self._service.greet()

    async def chat(self, request: ChatRequest) -> ChatReply | GuardrailRejection:
        return await self._service.chat(request)

    async def get_history(self, request: GetHistoryRequest) -> SessionHistory | None:
        return await self._service.get_history(request)

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        return await self._service.run(request)
