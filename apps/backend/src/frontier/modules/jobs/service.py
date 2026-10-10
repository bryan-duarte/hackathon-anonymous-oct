from datetime import UTC, datetime
from uuid import uuid4

import aiosqlite

from frontier.contracts.jobs import (
    AppendEventRequest,
    CreateJobRequest,
    FailUnfinishedRequest,
    FailUnfinishedResult,
    GetJobRequest,
    Job,
    JobEvent,
    JobPhase,
    JobStatus,
    UpdateJobRequest,
)
from frontier.modules.jobs.repository import JobsRepository

EVENTS_LIMIT = 50


class JobNotFoundError(LookupError):
    pass


class JobsService:
    """Durable state of migration jobs: status, phase, result and event log."""

    def __init__(self, repository: JobsRepository) -> None:
        self._repository = repository

    async def create(self, request: CreateJobRequest) -> Job:
        job_id = uuid4().hex
        now = _now()
        await self._repository.insert_job(
            {
                "id": job_id,
                "status": JobStatus.QUEUED.value,
                "phase": JobPhase.PENDING.value,
                **request.model_dump(),
                "created_at": now,
                "updated_at": now,
            }
        )
        await self._repository.insert_event(job_id, now, JobPhase.PENDING.value, "job queued")
        return await self._require(job_id)

    async def get(self, request: GetJobRequest) -> Job | None:
        return await self._load(request.job_id)

    async def update(self, request: UpdateJobRequest) -> Job:
        fields = request.model_dump(mode="json", exclude={"job_id"}, exclude_none=True)
        await self._repository.update_job(request.job_id, fields, _now())
        return await self._require(request.job_id)

    async def append_event(self, request: AppendEventRequest) -> JobEvent:
        at = _now()
        await self._repository.insert_event(
            request.job_id, at, request.phase.value, request.message
        )
        return JobEvent(at=datetime.fromisoformat(at), phase=request.phase, message=request.message)

    async def fail_unfinished(self, request: FailUnfinishedRequest) -> FailUnfinishedResult:
        job_ids = await self._repository.unfinished_job_ids()
        for job_id in job_ids:
            job = await self.update(
                UpdateJobRequest(job_id=job_id, status=JobStatus.FAILED, error=request.reason)
            )
            await self.append_event(
                AppendEventRequest(job_id=job_id, phase=job.phase, message=request.reason)
            )
        return FailUnfinishedResult(failed_count=len(job_ids))

    async def _require(self, job_id: str) -> Job:
        job = await self._load(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    async def _load(self, job_id: str) -> Job | None:
        row = await self._repository.get_job(job_id)
        if row is None:
            return None
        events = await self._repository.latest_events(job_id, EVENTS_LIMIT)
        return _to_job(row, events)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _to_job(row: aiosqlite.Row, events: list[aiosqlite.Row]) -> Job:
    return Job(
        id=row["id"],
        status=JobStatus(row["status"]),
        phase=JobPhase(row["phase"]),
        base_url=row["base_url"],
        context=row["context"],
        service_key_ref=row["service_key_ref"],
        team_token_ref=row["team_token_ref"],
        deployed_url=row["deployed_url"],
        error=row["error"],
        events=[
            JobEvent(
                at=datetime.fromisoformat(event["at"]),
                phase=JobPhase(event["phase"]),
                message=event["message"],
            )
            for event in events
        ],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
