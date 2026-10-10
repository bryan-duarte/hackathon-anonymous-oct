from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from frontier.contracts._base import ApiModel, StrictModel

Role = Literal["system", "user", "assistant", "tool"]

DEFAULT_HISTORY_LIMIT = 100

SessionId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,128}$")]


class SessionMessage(ApiModel):
    role: Role
    content: str


class GetHistoryRequest(StrictModel):
    session_id: SessionId
    limit: int = Field(default=DEFAULT_HISTORY_LIMIT, gt=0)


class SessionHistory(ApiModel):
    session_id: str
    messages: list[SessionMessage]
