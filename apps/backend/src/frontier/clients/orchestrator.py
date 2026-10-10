from typing import TYPE_CHECKING

from frontier.contracts.orchestrator import RunMigrationRequest, RunMigrationResult

if TYPE_CHECKING:
    from frontier.modules.orchestrator import OrchestratorService


class OrchestratorClient:
    def __init__(self, service: "OrchestratorService") -> None:
        self._service = service

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        return await self._service.run(request)
