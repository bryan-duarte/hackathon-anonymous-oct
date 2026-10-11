"""Composition root: the only place that instantiates module services."""

from dataclasses import dataclass

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver

from frontier.clients.deployer import DeployerClient
from frontier.clients.guardrails import GuardrailsClient
from frontier.clients.jobs import JobsClient
from frontier.clients.llm import LlmClient
from frontier.clients.mcp import McpClient
from frontier.clients.memory import MemoryClient
from frontier.clients.migrations import MigrationsClient
from frontier.clients.orchestrator import OrchestratorClient
from frontier.clients.prompts import PromptsClient
from frontier.clients.sandbox import SandboxClient
from frontier.clients.secrets import SecretsClient
from frontier.clients.sessions import SessionsClient
from frontier.clients.subagents import SubagentsClient
from frontier.clients.tools import ToolsClient
from frontier.contracts.llm import AgentRole
from frontier.core.config import Settings
from frontier.modules.deployer import DeployerService
from frontier.modules.guardrails import DecisionModel, GuardrailsService
from frontier.modules.jobs import JobsRepository, JobsService
from frontier.modules.llm_gateway import LlmGatewayService
from frontier.modules.mcp_gateway import McpGatewayService
from frontier.modules.memory import MemoryService
from frontier.modules.migrations import MigrationsService
from frontier.modules.orchestrator import OrchestratorService
from frontier.modules.prompts import PromptsService
from frontier.modules.sandbox import DockerDriver, SandboxDriver, SandboxService, VercelDriver
from frontier.modules.secrets import SecretsRepository, SecretsService
from frontier.modules.sessions import SessionsService
from frontier.modules.subagents import SubagentsService
from frontier.modules.tools import ToolsService


@dataclass(frozen=True)
class Clients:
    migrations: MigrationsClient
    jobs: JobsClient
    secrets: SecretsClient
    guardrails: GuardrailsClient
    orchestrator: OrchestratorClient
    subagents: SubagentsClient
    llm: LlmClient
    prompts: PromptsClient
    tools: ToolsClient
    mcp: McpClient
    memory: MemoryClient
    sessions: SessionsClient
    sandbox: SandboxClient
    deployer: DeployerClient


async def build_clients(
    settings: Settings, conn: aiosqlite.Connection, checkpointer: BaseCheckpointSaver
) -> Clients:
    jobs_repository = JobsRepository(conn)
    secrets_repository = SecretsRepository(conn)
    await jobs_repository.init_schema()
    await secrets_repository.init_schema()

    jobs = JobsClient(JobsService(jobs_repository))
    secrets = SecretsClient(SecretsService(secrets_repository, settings.secrets_master_key))
    guardrails = GuardrailsClient(
        GuardrailsService(
            decision_model=DecisionModel(
                api_key=settings.openrouter_api_key,
                url=settings.guardrail_url,
                model=settings.guardrail_model,
                timeout_s=settings.guardrail_timeout_s,
            ),
            block_threshold=settings.guardrail_block_threshold,
            chunk_chars=settings.guardrail_chunk_chars,
        )
    )
    llm = LlmClient(
        LlmGatewayService(
            api_key=settings.openrouter_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            models_by_role=_models_by_role(settings),
            max_tokens=settings.llm_max_tokens,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    )
    prompts = PromptsClient(PromptsService())
    sandbox = SandboxClient(
        SandboxService(
            driver=_sandbox_driver(settings),
            timeout_s=settings.sandbox_timeout_s,
            job_timeout_s=settings.migration_sandbox_timeout_s,
            secrets=secrets,
        )
    )
    tools = ToolsClient(
        ToolsService(
            secrets=secrets, jobs=jobs, sandbox=sandbox, probe_timeout_s=settings.probe_timeout_s
        )
    )
    subagents = SubagentsClient(SubagentsService(prompts=prompts, llm=llm))
    sessions = SessionsClient(SessionsService(checkpointer))
    orchestrator = OrchestratorClient(
        OrchestratorService(
            llm=llm,
            prompts=prompts,
            sandbox=sandbox,
            sessions=sessions,
            guardrails=guardrails,
            tools=tools,
            subagents=subagents,
            artifacts_dir=settings.artifacts_dir,
            sandbox_timeout_s=settings.migration_sandbox_timeout_s,
            max_phase_attempts=settings.migration_max_phase_attempts,
        )
    )
    migrations = MigrationsClient(
        MigrationsService(
            guardrails=guardrails,
            secrets=secrets,
            jobs=jobs,
            orchestrator=orchestrator,
            max_concurrent_jobs=settings.max_concurrent_jobs,
        )
    )

    return Clients(
        migrations=migrations,
        jobs=jobs,
        secrets=secrets,
        guardrails=guardrails,
        orchestrator=orchestrator,
        subagents=subagents,
        llm=llm,
        prompts=prompts,
        tools=tools,
        mcp=McpClient(McpGatewayService()),
        memory=MemoryClient(MemoryService()),
        sessions=sessions,
        sandbox=sandbox,
        deployer=DeployerClient(DeployerService()),
    )


def _models_by_role(settings: Settings) -> dict[AgentRole, str]:
    return {
        AgentRole.ORCHESTRATOR: settings.orchestrator_model or settings.llm_model,
        AgentRole.ANALYST: settings.analyst_model or settings.llm_model,
        AgentRole.SCIENTIST: settings.scientist_model or settings.llm_model,
        AgentRole.CODER: settings.coder_model or settings.llm_model,
    }


def _sandbox_driver(settings: Settings) -> SandboxDriver:
    if settings.sandbox_provider == "docker":
        return DockerDriver(
            image=settings.sandbox_docker_image,
            command_timeout_s=settings.sandbox_command_timeout_s,
        )
    return VercelDriver(
        token=settings.vercel_token,
        team_id=settings.vercel_team_id,
        project_id=settings.vercel_project_id,
        runtime=settings.sandbox_runtime,
        command_timeout_s=settings.sandbox_command_timeout_s,
    )
