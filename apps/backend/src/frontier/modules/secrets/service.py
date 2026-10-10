from secrets import token_hex

from cryptography.fernet import Fernet
from pydantic import SecretStr

from frontier.contracts.secrets import (
    RedactedText,
    RedactRequest,
    ResolvedSecret,
    ResolveSecretRequest,
    SecretHandle,
    StoreSecretRequest,
)
from frontier.modules.secrets.repository import SecretsRepository


class SecretNotFoundError(LookupError):
    pass


class SecretsService:
    """Encrypted secret vault. Callers only ever hold opaque `sec_…` handles."""

    def __init__(self, repository: SecretsRepository, master_key: SecretStr) -> None:
        self._repository = repository
        self._fernet = Fernet(master_key.get_secret_value().encode())

    async def store(self, request: StoreSecretRequest) -> SecretHandle:
        ref = f"sec_{token_hex(16)}"
        ciphertext = self._fernet.encrypt(request.value.get_secret_value().encode())
        await self._repository.insert(ref, request.label, ciphertext)
        return SecretHandle(ref=ref)

    async def resolve(self, request: ResolveSecretRequest) -> ResolvedSecret:
        _, value = await self._load(request.ref)
        return ResolvedSecret(ref=request.ref, value=SecretStr(value))

    async def redact(self, request: RedactRequest) -> RedactedText:
        text = request.text
        for ref in request.refs:
            label, value = await self._load(ref)
            text = text.replace(value, f"[REDACTED:{label}]")
        return RedactedText(text=text)

    async def _load(self, ref: str) -> tuple[str, str]:
        stored = await self._repository.get(ref)
        if stored is None:
            raise SecretNotFoundError(ref)
        label, ciphertext = stored
        return label, self._fernet.decrypt(ciphertext).decode()
