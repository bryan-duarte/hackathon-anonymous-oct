from collections.abc import Awaitable, Callable

from langchain_core.tools import BaseTool, StructuredTool

from frontier.clients.jobs import JobsClient
from frontier.clients.sandbox import SandboxClient
from frontier.clients.secrets import SecretsClient
from frontier.contracts.tools import MigrationToolset
from frontier.modules.tools.characterization import CharacterizationRunner
from frontier.modules.tools.legacy_api import LegacyApiProbe
from frontier.modules.tools.middleware import ToolOutputGuardMiddleware
from frontier.modules.tools.progress import ProgressReporter


class ToolsService:
    """Host-side tools for the migration agents; credentials never leave the host."""

    def __init__(
        self,
        *,
        secrets: SecretsClient,
        jobs: JobsClient,
        sandbox: SandboxClient,
        probe_timeout_s: float,
    ) -> None:
        self._legacy_api = LegacyApiProbe(secrets=secrets, timeout_s=probe_timeout_s)
        self._characterization = CharacterizationRunner(sandbox=sandbox, secrets=secrets)
        self._progress = ProgressReporter(jobs=jobs, secrets=secrets)
        self._output_guard = ToolOutputGuardMiddleware(secrets=secrets)

    def migration_toolset(self) -> MigrationToolset:
        discover_endpoints = _as_tool(self._legacy_api.discover_endpoints, "discover_endpoints")
        probe_http = _as_tool(self._legacy_api.probe_http, "probe_http")
        run_characterization_suite = _as_tool(
            self._characterization.run_characterization_suite, "run_characterization_suite"
        )
        check_behavior_coverage = _as_tool(
            self._characterization.check_behavior_coverage, "check_behavior_coverage"
        )
        report_progress = _as_tool(self._progress.report_progress, "report_progress")
        return MigrationToolset(
            orchestrator=[run_characterization_suite, check_behavior_coverage, report_progress],
            analyst=[discover_endpoints, probe_http],
            scientist=[discover_endpoints, probe_http],
            coder=[probe_http, run_characterization_suite, check_behavior_coverage],
            output_guard=self._output_guard,
        )


def _as_tool(coroutine: Callable[..., Awaitable[str]], name: str) -> BaseTool:
    return StructuredTool.from_function(coroutine=coroutine, name=name)
