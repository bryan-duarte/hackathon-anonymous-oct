from datetime import datetime
from typing import Literal

from pydantic import Field

from frontier.contracts._base import StrictModel

Role = Literal["system", "user", "assistant", "tool"]


class AppendMessageRequest(StrictModel):
    session_id: str
    role: Role
    content: str


class SessionMessage(StrictModel):
    session_id: str
    role: Role
    content: str
    at: datetime


class GetHistoryRequest(StrictModel):
    session_id: str
    limit: int = Field(default=100, gt=0)


class SessionHistory(StrictModel):
    messages: list[SessionMessage]
