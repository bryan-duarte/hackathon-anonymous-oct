from deepagents import create_deep_agent
from deepagents.backends.protocol import BackendProtocol
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
from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailRejection
from frontier.contracts.orchestrator import (
    ChatReply,
    ChatRequest,
    RunMigrationRequest,
    RunMigrationResult,
)
from frontier.contracts.prompts import Greeting, PromptId
from frontier.contracts.sessions import GetHistoryRequest, SessionHistory
from frontier.modules.orchestrator.errors import MissingStructuredResponseError

STRUCTURED_RESPONSE_KEY = "structured_response"
MESSAGES_KEY = "messages"


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
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._sandbox = sandbox
        self._sessions = sessions
        self._guardrails = guardrails

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
        raise NotImplementedError("orchestrator.run")

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
