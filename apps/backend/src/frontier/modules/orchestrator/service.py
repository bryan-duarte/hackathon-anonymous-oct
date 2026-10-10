import asyncio
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware import FilesystemMiddleware
from langchain.agents.middleware import TodoListMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from frontier.clients.guardrails import GuardrailsClient
from frontier.clients.llm import LlmClient
from frontier.clients.prompts import PromptsClient
from frontier.clients.sandbox import SandboxClient
from frontier.clients.sessions import SessionsClient
from frontier.clients.subagents import SubagentsClient
from frontier.clients.tools import ToolsClient
from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailRejection
from frontier.contracts.llm import AgentRole
from frontier.contracts.orchestrator import (
    ChatReply,
    ChatRequest,
    RunMigrationRequest,
    RunMigrationResult,
)
from frontier.contracts.prompts import Greeting, MigrationVerdict, PromptId
from frontier.contracts.sandbox import (
    CreateSandboxRequest,
    ExportedWorkspace,
    ExportWorkspaceRequest,
    JobSandbox,
)
from frontier.contracts.sessions import GetHistoryRequest, SessionHistory
from frontier.contracts.tools import MigrationRunContext, MigrationToolset
from frontier.contracts.workspace import MIGRATION_WORKSPACE
from frontier.core.logging_config import get_logger
from frontier.modules.orchestrator.errors import (
    ArtifactExportFailedError,
    MigrationTimedOutError,
    MigrationTimeoutTooShortError,
    MissingStructuredResponseError,
    SkillUploadError,
)

logger = get_logger(__name__)

STRUCTURED_RESPONSE_KEY = "structured_response"
MESSAGES_KEY = "messages"
ARTIFACT_EXPORT_MARGIN_S = 180
LEADER_FILE_TOOLS = ["ls", "read_file", "glob", "grep", "execute"]
ORCHESTRATOR_AGENT_NAME = "migration-orchestrator"
MIGRATION_THREAD_PREFIX = "migration:"
KICKOFF_TEMPLATE = """\
Refactor the legacy API at {base_url} into a new version with identical behavior.

Context from the requester:
{context}

Attempt cap: at most {max_phase_attempts} attempts per phase.

Start by planning with write_todos.
"""


class OrchestratorService:
    """deepagents orchestrator: plans and drives the full black-box migration."""

    def __init__(
        self,
        *,
        llm: LlmClient,
        prompts: PromptsClient,
        sandbox: SandboxClient,
        sessions: SessionsClient,
        guardrails: GuardrailsClient,
        tools: ToolsClient,
        subagents: SubagentsClient,
        artifacts_dir: Path,
        sandbox_timeout_s: int,
        max_phase_attempts: int,
    ) -> None:
        run_timeout_s = sandbox_timeout_s - ARTIFACT_EXPORT_MARGIN_S
        export_margin_leaves_no_run_time = run_timeout_s <= 0
        if export_margin_leaves_no_run_time:
            raise MigrationTimeoutTooShortError(sandbox_timeout_s, ARTIFACT_EXPORT_MARGIN_S)

        self._llm = llm
        self._prompts = prompts
        self._sandbox = sandbox
        self._sessions = sessions
        self._guardrails = guardrails
        self._tools = tools
        self._subagents = subagents
        self._artifacts_dir = artifacts_dir
        self._run_timeout_s = run_timeout_s
        self._max_phase_attempts = max_phase_attempts

    async def greet(self) -> Greeting:
        greeting_task = self._prompts.get_text(PromptId.GREETING)
        greeting_schema = self._prompts.get_schema(PromptId.GREETING)
        async with self._sandbox.session() as backend:
            agent = self._build_agent(backend=backend, response_format=greeting_schema)
            final_state = await agent.ainvoke(
                {"messages": [{"role": "user", "content": greeting_task}]}
            )

        greeting = final_state.get(STRUCTURED_RESPONSE_KEY)
        if not isinstance(greeting, Greeting):
            raise MissingStructuredResponseError(Greeting)
        return greeting

    async def chat(self, request: ChatRequest) -> ChatReply | GuardrailRejection:
        verdict = await self._guardrails.check(GuardrailCheckRequest(context=request.message))
        if not verdict.allowed:
            return GuardrailRejection(violations=verdict.violations)

        session_id = request.session_id or self._sessions.new_session_id()
        async with self._sandbox.session() as backend:
            agent = self._build_agent(backend=backend, checkpointer=self._sessions.checkpointer())
            final_state = await agent.ainvoke(
                {MESSAGES_KEY: [{"role": "user", "content": request.message}]},
                config=_thread_config(session_id),
            )

        agent_reply = final_state[MESSAGES_KEY][-1]
        return ChatReply(session_id=session_id, reply=agent_reply.text)

    async def get_history(self, request: GetHistoryRequest) -> SessionHistory | None:
        agent = self._build_agent(checkpointer=self._sessions.checkpointer())
        snapshot = await agent.aget_state(_thread_config(request.session_id))
        session_was_never_started = snapshot.created_at is None
        if session_was_never_started:
            return None
        return self._sessions.build_history(
            request.session_id, snapshot.values.get(MESSAGES_KEY, []), request.limit
        )

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        sandbox_request = CreateSandboxRequest(job_id=request.job_id)
        async with self._sandbox.job_session(sandbox_request) as job_sandbox:
            await self._seed_coder_skills(job_sandbox)
            toolset = self._tools.migration_toolset()
            agent = self._build_migration_agent(job_sandbox=job_sandbox, toolset=toolset)
            context = MigrationRunContext(
                job_id=request.job_id,
                base_url=request.base_url,
                service_key_ref=request.service_key_ref,
                sandbox_id=job_sandbox.sandbox_id,
            )
            try:
                final_state = await self._invoke_with_deadline(agent, request, context)
            finally:
                exported_workspace = await self._export_artifacts(job_sandbox, request.job_id)

        migration_verdict = final_state.get(STRUCTURED_RESPONSE_KEY)
        if not isinstance(migration_verdict, MigrationVerdict):
            raise MissingStructuredResponseError(MigrationVerdict)
        if exported_workspace is None:
            raise ArtifactExportFailedError(request.job_id)
        return RunMigrationResult(
            verdict=migration_verdict.verdict,
            summary=migration_verdict.summary,
            artifacts_path=exported_workspace.path,
        )

    async def _seed_coder_skills(self, job_sandbox: JobSandbox) -> None:
        uploads = await job_sandbox.backend.aupload_files(self._subagents.skill_files())
        failed_paths = [upload.path for upload in uploads if upload.error is not None]
        if failed_paths:
            raise SkillUploadError(failed_paths)

    async def _invoke_with_deadline(
        self, agent: CompiledStateGraph, request: RunMigrationRequest, context: MigrationRunContext
    ) -> dict:
        kickoff = KICKOFF_TEMPLATE.format(
            base_url=request.base_url,
            context=request.context,
            max_phase_attempts=self._max_phase_attempts,
        )
        deadline = asyncio.timeout(self._run_timeout_s)
        try:
            async with deadline:
                return await agent.ainvoke(
                    {MESSAGES_KEY: [{"role": "user", "content": kickoff}]},
                    config=_migration_thread_config(request.job_id),
                    context=context,
                )
        except TimeoutError as error:
            if deadline.expired():
                raise MigrationTimedOutError(self._run_timeout_s) from error
            raise

    async def _export_artifacts(
        self, job_sandbox: JobSandbox, job_id: str
    ) -> ExportedWorkspace | None:
        try:
            exported_workspace = await self._sandbox.export(
                ExportWorkspaceRequest(
                    sandbox_id=job_sandbox.sandbox_id,
                    source_dir=MIGRATION_WORKSPACE,
                    destination_dir=str(self._artifacts_dir / job_id),
                )
            )
        except Exception:
            logger.exception("migration_artifacts_export_failed", job_id=job_id)
            return None
        logger.info(
            "migration_artifacts_exported", job_id=job_id, file_count=exported_workspace.file_count
        )
        return exported_workspace

    def _build_migration_agent(
        self, *, job_sandbox: JobSandbox, toolset: MigrationToolset
    ) -> CompiledStateGraph:
        return create_deep_agent(
            model=self._llm.chat_model_for(AgentRole.ORCHESTRATOR),
            tools=toolset.orchestrator,
            system_prompt=self._prompts.get_text(PromptId.MIGRATION_ORCHESTRATOR),
            middleware=[
                TodoListMiddleware(),
                FilesystemMiddleware(backend=job_sandbox.backend, tools=LEADER_FILE_TOOLS),
                toolset.output_guard,
            ],
            subagents=self._subagents.migration_subagents(toolset),
            backend=job_sandbox.backend,
            response_format=ToolStrategy(MigrationVerdict),
            context_schema=MigrationRunContext,
            checkpointer=self._sessions.checkpointer(),
            name=ORCHESTRATOR_AGENT_NAME,
        )

    def _build_agent(
        self,
        *,
        backend: BackendProtocol | None = None,
        response_format: type[BaseModel] | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> CompiledStateGraph:
        return create_deep_agent(
            model=self._llm.chat_model(),
            system_prompt=self._prompts.get_text(PromptId.MIGRATION_AGENT),
            backend=backend,
            response_format=ToolStrategy(response_format) if response_format else None,
            checkpointer=checkpointer,
        )


def _thread_config(session_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": session_id}}


def _migration_thread_config(job_id: str) -> RunnableConfig:
    return _thread_config(f"{MIGRATION_THREAD_PREFIX}{job_id}")
