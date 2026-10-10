from pydantic import Field

from frontier.contracts._base import ApiModel, StrictModel
from frontier.contracts.sessions import SessionId

MAX_CHAT_MESSAGE_LENGTH = 200_000


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
    message: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_LENGTH)


class ChatReply(ApiModel):
    session_id: str
    reply: str
