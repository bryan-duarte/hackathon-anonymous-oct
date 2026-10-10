from pydantic import SecretStr

from frontier.contracts._base import StrictModel


class StoreSecretRequest(StrictModel):
    label: str
    value: SecretStr


class SecretHandle(StrictModel):
    ref: str


class ResolveSecretRequest(StrictModel):
    ref: str


class ResolvedSecret(StrictModel):
    ref: str
    value: SecretStr


class RedactRequest(StrictModel):
    text: str
    refs: list[str]


class RedactedText(StrictModel):
    text: str
