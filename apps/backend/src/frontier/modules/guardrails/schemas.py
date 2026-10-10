import re
from typing import Literal

from pydantic import BaseModel, Field

from frontier.contracts._base import StrictModel
from frontier.contracts.guardrails import GuardrailViolation, GuardrailViolationCode


class SecretPattern(StrictModel):
    label: str
    regex: re.Pattern[str]


class SecretMatch(StrictModel):
    label: str
    start: int
    end: int


class ScreeningState(StrictModel):
    task: str
    base_url: str | None
    context: str


class YesNoCriteria(StrictModel):
    true: str
    false: str


class YesNoQuestion(StrictModel):
    type: Literal["noul"] = "noul"
    instructions: str
    criteria: YesNoCriteria


class RiskPolicy(StrictModel):
    code: GuardrailViolationCode
    question: YesNoQuestion
    violation: GuardrailViolation


class DecisionsRequest(StrictModel):
    model: str
    state: ScreeningState
    questions: dict[str, YesNoQuestion]


class YesNoAnswer(BaseModel):
    type: Literal["noul"]
    noul: float = Field(ge=0, le=1)


class DecisionsResponse(BaseModel):
    answers: dict[str, YesNoAnswer]
