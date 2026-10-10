from typing import TYPE_CHECKING

from deepagents import SubAgent

from frontier.contracts.tools import MigrationToolset

if TYPE_CHECKING:
    from frontier.modules.subagents import SubagentsService


class SubagentsClient:
    def __init__(self, service: "SubagentsService") -> None:
        self._service = service

    def migration_subagents(self, toolset: MigrationToolset) -> list[SubAgent]:
        return self._service.migration_subagents(toolset)

    def skill_files(self) -> list[tuple[str, bytes]]:
        return self._service.skill_files()
