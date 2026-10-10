from datetime import datetime

from pydantic import Field, HttpUrl, SecretStr

from frontier.contracts._base import MAX_AGENT_INPUT_LENGTH, ApiModel
from frontier.contracts.jobs import JobEvent, JobPhase, JobStatus, MigrationVerdictKind

MIN_SECRET_LENGTH = 8


class MigrationRequest(ApiModel):
    base_url: HttpUrl
    service_key: SecretStr = Field(min_length=MIN_SECRET_LENGTH)
    team_token: SecretStr = Field(min_length=MIN_SECRET_LENGTH)
    context: str = Field(min_length=1, max_length=MAX_AGENT_INPUT_LENGTH)


class MigrationAccepted(ApiModel):
    job_id: str
    status: JobStatus
    status_url: str


class GetMigrationStatusRequest(ApiModel):
    job_id: str


class MigrationStatus(ApiModel):
    job_id: str
    status: JobStatus
    phase: JobPhase
    events: list[JobEvent]
    deployed_url: str | None
    error: str | None
    verdict: MigrationVerdictKind | None
    summary: str | None
    artifacts_path: str | None
    created_at: datetime
    updated_at: datetime
