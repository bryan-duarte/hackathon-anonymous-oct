from datetime import datetime

from pydantic import Field, HttpUrl, SecretStr

from frontier.contracts._base import ApiModel
from frontier.contracts.jobs import JobEvent, JobPhase, JobStatus


class MigrationRequest(ApiModel):
    base_url: HttpUrl
    service_key: SecretStr = Field(min_length=1)
    team_token: SecretStr = Field(min_length=1)
    context: str = Field(min_length=1, max_length=200_000)


class MigrationAccepted(ApiModel):
    job_id: str
    status: JobStatus
    status_url: str


class MigrationRejected(ApiModel):
    reasons: list[str]


class GetMigrationStatusRequest(ApiModel):
    job_id: str


class MigrationStatus(ApiModel):
    job_id: str
    status: JobStatus
    phase: JobPhase
    events: list[JobEvent]
    deployed_url: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
