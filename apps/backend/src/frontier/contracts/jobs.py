from datetime import datetime
from enum import StrEnum

from frontier.contracts._base import StrictModel


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobPhase(StrEnum):
    PENDING = "pending"
    API_ANALYSIS = "api_analysis"
    BEHAVIOR_ANALYSIS = "behavior_analysis"
    CHARACTERIZATION = "characterization"
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"
    DISCOVERY = "discovery"
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"
    DONE = "done"


class MigrationVerdictKind(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class JobEvent(StrictModel):
    at: datetime
    phase: JobPhase
    message: str


class Job(StrictModel):
    id: str
    status: JobStatus
    phase: JobPhase
    base_url: str
    context: str
    service_key_ref: str
    team_token_ref: str
    deployed_url: str | None
    error: str | None
    verdict: MigrationVerdictKind | None
    summary: str | None
    artifacts_path: str | None
    events: list[JobEvent]
    created_at: datetime
    updated_at: datetime


class CreateJobRequest(StrictModel):
    base_url: str
    context: str
    service_key_ref: str
    team_token_ref: str


class GetJobRequest(StrictModel):
    job_id: str


class UpdateJobRequest(StrictModel):
    job_id: str
    status: JobStatus | None = None
    phase: JobPhase | None = None
    deployed_url: str | None = None
    error: str | None = None
    verdict: MigrationVerdictKind | None = None
    summary: str | None = None
    artifacts_path: str | None = None


class AppendEventRequest(StrictModel):
    job_id: str
    phase: JobPhase
    message: str


class FailUnfinishedRequest(StrictModel):
    reason: str


class FailUnfinishedResult(StrictModel):
    failed_count: int
