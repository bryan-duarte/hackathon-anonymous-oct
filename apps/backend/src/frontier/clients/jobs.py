from typing import TYPE_CHECKING

from frontier.contracts.jobs import (
    AppendEventRequest,
    CreateJobRequest,
    FailUnfinishedRequest,
    FailUnfinishedResult,
    GetJobRequest,
    Job,
    JobEvent,
    UpdateJobRequest,
)

if TYPE_CHECKING:
    from frontier.modules.jobs import JobsService


class JobsClient:
    def __init__(self, service: "JobsService") -> None:
        self._service = service

    async def create(self, request: CreateJobRequest) -> Job:
        return await self._service.create(request)

    async def get(self, request: GetJobRequest) -> Job | None:
        return await self._service.get(request)

    async def update(self, request: UpdateJobRequest) -> Job:
        return await self._service.update(request)

    async def append_event(self, request: AppendEventRequest) -> JobEvent:
        return await self._service.append_event(request)

    async def fail_unfinished(self, request: FailUnfinishedRequest) -> FailUnfinishedResult:
        return await self._service.fail_unfinished(request)
