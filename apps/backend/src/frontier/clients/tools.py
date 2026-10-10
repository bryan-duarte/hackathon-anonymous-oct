from typing import TYPE_CHECKING

from frontier.contracts.tools import MigrationToolset

if TYPE_CHECKING:
    from frontier.modules.tools import ToolsService


class ToolsClient:
    def __init__(self, service: "ToolsService") -> None:
        self._service = service

    def migration_toolset(self) -> MigrationToolset:
        return self._service.migration_toolset()
