from typing import TYPE_CHECKING

from frontier.contracts.migrations import (
    GetMigrationStatusRequest,
    MigrationAccepted,
    MigrationRejected,
    MigrationRequest,
    MigrationStatus,
)

if TYPE_CHECKING:
    from frontier.modules.migrations import MigrationsService


class MigrationsClient:
    def __init__(self, service: "MigrationsService") -> None:
        self._service = service

    async def submit(self, request: MigrationRequest) -> MigrationAccepted | MigrationRejected:
        return await self._service.submit(request)

    async def get_status(self, request: GetMigrationStatusRequest) -> MigrationStatus | None:
        return await self._service.get_status(request)

    async def shutdown(self) -> None:
        await self._service.shutdown()
