from typing import Literal

from langchain.tools import ToolRuntime

from frontier.clients.jobs import JobsClient
from frontier.clients.secrets import SecretsClient
from frontier.contracts.jobs import AppendEventRequest, JobPhase, UpdateJobRequest
from frontier.contracts.tools import MigrationRunContext
from frontier.modules.tools.redaction import redact_for_run

ReportablePhase = Literal[
    "api_analysis", "behavior_analysis", "characterization", "implementation", "validation"
]


class ProgressReporter:
    """Records the orchestrator's phase transitions on the migration job."""

    def __init__(self, *, jobs: JobsClient, secrets: SecretsClient) -> None:
        self._jobs = jobs
        self._secrets = secrets

    async def report_progress(
        self, phase: ReportablePhase, message: str, runtime: ToolRuntime[MigrationRunContext]
    ) -> str:
        """Record a phase transition or milestone on the migration job."""
        context = runtime.context
        job_phase = JobPhase(phase)
        redacted_message = await redact_for_run(self._secrets, message, context)
        await self._jobs.update(UpdateJobRequest(job_id=context.job_id, phase=job_phase))
        await self._jobs.append_event(
            AppendEventRequest(job_id=context.job_id, phase=job_phase, message=redacted_message)
        )
        return "recorded"
