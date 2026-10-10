from enum import StrEnum

from pydantic import Field, SecretStr, computed_field

from frontier.contracts._base import ApiModel, StrictModel


class GuardrailCheckRequest(StrictModel):
    context: str
    base_url: str | None = None
    secrets: dict[str, SecretStr] = Field(default_factory=dict)


class GuardrailViolationCode(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    EXPOSED_SECRET = "exposed_secret"
    OFF_MISSION = "off_mission"
    HARMFUL_REQUEST = "harmful_request"


class GuardrailViolation(StrictModel):
    code: GuardrailViolationCode
    title: str
    message: str


class GuardrailVerdict(StrictModel):
    allowed: bool
    violations: list[GuardrailViolation]


class GuardrailRejection(ApiModel):
    violations: list[GuardrailViolation]

    @computed_field
    @property
    def reasons(self) -> list[str]:
        return [violation.message for violation in self.violations]
