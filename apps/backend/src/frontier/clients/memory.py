from typing import TYPE_CHECKING

from frontier.contracts.memory import (
    MemoryRecord,
    MemoryResults,
    SaveMemoryRequest,
    SearchMemoryRequest,
)

if TYPE_CHECKING:
    from frontier.modules.memory import MemoryService


class MemoryClient:
    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    async def save(self, request: SaveMemoryRequest) -> MemoryRecord:
        return await self._service.save(request)

    async def search(self, request: SearchMemoryRequest) -> MemoryResults:
        return await self._service.search(request)
