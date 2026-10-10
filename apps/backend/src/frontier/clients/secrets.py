from typing import TYPE_CHECKING

from frontier.contracts.secrets import (
    RedactedText,
    RedactRequest,
    ResolvedSecret,
    ResolveSecretRequest,
    SecretHandle,
    StoreSecretRequest,
)

if TYPE_CHECKING:
    from frontier.modules.secrets import SecretsService


class SecretsClient:
    def __init__(self, service: "SecretsService") -> None:
        self._service = service

    async def store(self, request: StoreSecretRequest) -> SecretHandle:
        return await self._service.store(request)

    async def resolve(self, request: ResolveSecretRequest) -> ResolvedSecret:
        return await self._service.resolve(request)

    async def redact(self, request: RedactRequest) -> RedactedText:
        return await self._service.redact(request)
