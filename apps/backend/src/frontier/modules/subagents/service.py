from frontier.contracts.subagents import DelegateTaskRequest, DelegateTaskResult


class SubagentsService:
    """Specialised subagents that split load and bound context consumption."""

    async def delegate(self, request: DelegateTaskRequest) -> DelegateTaskResult:
        raise NotImplementedError("subagents.delegate")
