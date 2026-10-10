from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field

BEHAVIOR_ID_PATTERN = r"^B-\d+$"


class CatalogueBehavior(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str = Field(pattern=BEHAVIOR_ID_PATTERN)


class BehaviorCatalogue(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    behaviors: list[CatalogueBehavior]


class PathReport(NamedTuple):
    exists: bool
    line: str
