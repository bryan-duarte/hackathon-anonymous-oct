from typing import TYPE_CHECKING

from frontier.contracts.orchestrator import RunMigrationRequest, RunMigrationResult
from frontier.contracts.prompts import Greeting

if TYPE_CHECKING:
    from frontier.modules.orchestrator import OrchestratorService


class OrchestratorClient:
    def __init__(self, service: "OrchestratorService") -> None:
        self._service = service

    async def greet(self) -> Greeting:
        return await self._service.greet()

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        return await self._service.run(request)
