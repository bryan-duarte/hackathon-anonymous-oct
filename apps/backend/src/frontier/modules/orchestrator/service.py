from deepagents import create_deep_agent
from deepagents.backends.protocol import BackendProtocol
from langchain.agents.structured_output import ToolStrategy
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from frontier.clients.llm import LlmClient
from frontier.clients.prompts import PromptsClient
from frontier.clients.sandbox import SandboxClient
from frontier.contracts.orchestrator import RunMigrationRequest, RunMigrationResult
from frontier.contracts.prompts import Greeting, PromptId
from frontier.modules.orchestrator.errors import MissingStructuredResponseError

STRUCTURED_RESPONSE_KEY = "structured_response"


class OrchestratorService:
    """deepagents orchestrator: plans and drives the full black-box migration."""

    def __init__(self, *, llm: LlmClient, prompts: PromptsClient, sandbox: SandboxClient) -> None:
        self._llm = llm
        self._prompts = prompts
        self._sandbox = sandbox

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

    async def run(self, request: RunMigrationRequest) -> RunMigrationResult:
        raise NotImplementedError("orchestrator.run")

    def _build_agent(
        self, *, backend: BackendProtocol, response_format: type[BaseModel]
    ) -> CompiledStateGraph:
        return create_deep_agent(
            model=self._llm.chat_model(),
            system_prompt=self._prompts.get_text(PromptId.MIGRATION_AGENT),
            backend=backend,
            response_format=ToolStrategy(response_format),
        )
