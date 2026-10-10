from frontier.contracts.orchestrator import RunMigrationRequest, RunMigrationResult


class OrchestratorService:
    """deepagents orchestrator: plans and drives the full black-box migration."""

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        raise NotImplementedError("orchestrator.run")
