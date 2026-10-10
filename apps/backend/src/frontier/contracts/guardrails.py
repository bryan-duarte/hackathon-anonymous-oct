from enum import StrEnum

from pydantic import SecretStr

from frontier.contracts._base import StrictModel


class GuardrailCheckRequest(StrictModel):
    base_url: str
    context: str
    secrets: dict[str, SecretStr]


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
