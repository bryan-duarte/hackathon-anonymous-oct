from frontier.contracts.memory import (
    MemoryRecord,
    MemoryResults,
    SaveMemoryRequest,
    SearchMemoryRequest,
)


class MemoryService:
    """Long-term memory per migration project: artifacts, state and history."""

    async def save(self, request: SaveMemoryRequest) -> MemoryRecord:
        raise NotImplementedError("memory.save")

    async def search(self, request: SearchMemoryRequest) -> MemoryResults:
        raise NotImplementedError("memory.search")
