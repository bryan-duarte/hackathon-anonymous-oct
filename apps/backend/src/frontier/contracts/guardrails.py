from pydantic import SecretStr

from frontier.contracts._base import StrictModel


class GuardrailCheckRequest(StrictModel):
    base_url: str
    context: str
    secrets: dict[str, SecretStr]


class GuardrailVerdict(StrictModel):
    allowed: bool
    reasons: list[str]
