from pydantic import Field

from frontier.contracts._base import MAX_AGENT_INPUT_LENGTH, ApiModel, StrictModel
from frontier.contracts.sessions import SessionId


class RunMigrationRequest(StrictModel):
    job_id: str
    base_url: str
    context: str
    service_key_ref: str
    team_token_ref: str


class RunMigrationResult(StrictModel):
    deployed_url: str


class ChatRequest(ApiModel):
    session_id: SessionId | None = None
    message: str = Field(min_length=1, max_length=MAX_AGENT_INPUT_LENGTH)


class ChatReply(ApiModel):
    session_id: str
    reply: str
