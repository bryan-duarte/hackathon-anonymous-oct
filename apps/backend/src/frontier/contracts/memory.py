from datetime import datetime

from pydantic import Field

from frontier.contracts._base import StrictModel


class SaveMemoryRequest(StrictModel):
    project_key: str
    key: str
    content: str


class MemoryRecord(StrictModel):
    project_key: str
    key: str
    content: str
    updated_at: datetime


class SearchMemoryRequest(StrictModel):
    project_key: str
    query: str
    limit: int = Field(default=10, gt=0)


class MemoryResults(StrictModel):
    records: list[MemoryRecord]
