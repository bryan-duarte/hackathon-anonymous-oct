import asyncio
import logging

from frontier.clients.guardrails import GuardrailsClient
from frontier.clients.jobs import JobsClient
from frontier.clients.orchestrator import OrchestratorClient
from frontier.clients.secrets import SecretsClient
from frontier.contracts.guardrails import GuardrailCheckRequest
from frontier.contracts.jobs import (
    AppendEventRequest,
    CreateJobRequest,
    GetJobRequest,
    Job,
    JobPhase,
    JobStatus,
    UpdateJobRequest,
)
from frontier.contracts.migrations import (
    GetMigrationStatusRequest,
    MigrationAccepted,
    MigrationRejected,
    MigrationRequest,
    MigrationStatus,
)
from frontier.contracts.orchestrator import RunMigrationRequest
from frontier.contracts.secrets import RedactRequest, StoreSecretRequest

logger = logging.getLogger(__name__)


class MigrationsService:
    """Submit workflow: guardrails -> secret vault -> job -> background orchestrator run."""

    def __init__(
        self,
        guardrails: GuardrailsClient,
        secrets: SecretsClient,
        jobs: JobsClient,
        orchestrator: OrchestratorClient,
        max_concurrent_jobs: int,
    ) -> None:
        self._guardrails = guardrails
        self._secrets = secrets
        self._jobs = jobs
        self._orchestrator = orchestrator
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit(self, request: MigrationRequest) -> MigrationAccepted | MigrationRejected:
        base_url = str(request.base_url)
        verdict = await self._guardrails.check(
            GuardrailCheckRequest(
                base_url=base_url,
                context=request.context,
                secrets={"service_key": request.service_key, "team_token": request.team_token},
            )
        )
        if not verdict.allowed:
            return MigrationRejected(reasons=verdict.reasons)

        service_key = await self._secrets.store(
            StoreSecretRequest(label="service_key", value=request.service_key)
        )
        team_token = await self._secrets.store(
            StoreSecretRequest(label="team_token", value=request.team_token)
        )
        job = await self._jobs.create(
            CreateJobRequest(
                base_url=base_url,
                context=request.context,
                service_key_ref=service_key.ref,
                team_token_ref=team_token.ref,
            )
        )

        task = asyncio.create_task(self._run(job))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        return MigrationAccepted(
            job_id=job.id, status=job.status, status_url=f"/migrations/{job.id}"
        )

    async def get_status(self, request: GetMigrationStatusRequest) -> MigrationStatus | None:
        job = await self._jobs.get(GetJobRequest(job_id=request.job_id))
        if job is None:
            return None
        return MigrationStatus(
            job_id=job.id,
            status=job.status,
            phase=job.phase,
            events=job.events,
            deployed_url=job.deployed_url,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _run(self, job: Job) -> None:
        async with self._semaphore:
            try:
                await self._jobs.update(
                    UpdateJobRequest(
                        job_id=job.id, status=JobStatus.RUNNING, phase=JobPhase.DISCOVERY
                    )
                )
                await self._jobs.append_event(
                    AppendEventRequest(
                        job_id=job.id, phase=JobPhase.DISCOVERY, message="orchestrator started"
                    )
                )
                result = await self._orchestrator.run(
                    RunMigrationRequest(
                        job_id=job.id,
                        base_url=job.base_url,
                        context=job.context,
                        service_key_ref=job.service_key_ref,
                        team_token_ref=job.team_token_ref,
                    )
                )
            except Exception as exc:
                await self._fail(job, exc)
                return

            await self._jobs.update(
                UpdateJobRequest(
                    job_id=job.id,
                    status=JobStatus.SUCCEEDED,
                    phase=JobPhase.DONE,
                    deployed_url=result.deployed_url,
                )
            )
            await self._jobs.append_event(
                AppendEventRequest(
                    job_id=job.id,
                    phase=JobPhase.DONE,
                    message=f"deployed at {result.deployed_url}",
                )
            )

    async def _fail(self, job: Job, exc: Exception) -> None:
        # Exception text may echo upstream responses, so scrub secrets before persisting it.
        redacted = await self._secrets.redact(
            RedactRequest(
                text=f"{type(exc).__name__}: {exc}",
                refs=[job.service_key_ref, job.team_token_ref],
            )
        )
        logger.warning("migration %s failed: %s", job.id, redacted.text)
        failed = await self._jobs.update(
            UpdateJobRequest(job_id=job.id, status=JobStatus.FAILED, error=redacted.text)
        )
        await self._jobs.append_event(
            AppendEventRequest(job_id=job.id, phase=failed.phase, message=redacted.text)
        )
