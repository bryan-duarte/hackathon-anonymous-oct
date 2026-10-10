from typing import TYPE_CHECKING

from frontier.contracts.subagents import DelegateTaskRequest, DelegateTaskResult

if TYPE_CHECKING:
    from frontier.modules.subagents import SubagentsService


class SubagentsClient:
    def __init__(self, service: "SubagentsService") -> None:
        self._service = service

    async def delegate(self, request: DelegateTaskRequest) -> DelegateTaskResult:
        return await self._service.delegate(request)
