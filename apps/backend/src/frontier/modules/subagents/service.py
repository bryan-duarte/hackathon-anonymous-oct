from collections.abc import Sequence
from importlib.resources import files
from importlib.resources.abc import Traversable

from deepagents import SubAgent
from langchain.agents.middleware import AgentMiddleware, TodoListMiddleware
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.tools import BaseTool

from frontier.clients.llm import LlmClient
from frontier.clients.prompts import PromptsClient
from frontier.contracts.llm import AgentRole
from frontier.contracts.prompts import PromptId
from frontier.contracts.tools import MigrationToolset
from frontier.contracts.workspace import CODER_SKILLS_SOURCE

API_ANALYST_NAME = "api-analyst"
API_SCIENTIST_NAME = "api-scientist"
CODER_NAME = "coder"
VENDORED_SKILLS_PACKAGE = "frontier.modules.subagents"
VENDORED_SKILLS_DIR = "skills"

API_ANALYST_DESCRIPTION = (
    "Documents the legacy API surface: OpenAPI/spec discovery, endpoints, auth scheme, response "
    "and error formats. Writes reports/01-api-surface.md."
)
API_SCIENTIST_DESCRIPTION = (
    "Experiments against the legacy API to document every endpoint's input/output schema, edge "
    "cases and error cases as behaviors B-NNN. Writes reports/02-behavior.md and "
    "reports/behaviors.json."
)
CODER_DESCRIPTION = (
    "Writes code following the codebase-change skill. Mode 1: characterization test suite only. "
    "Mode 2: implements the new API version until the suite passes against it."
)


class SubagentsService:
    """Specialist refactoring subagents: API analyst, API scientist and coder."""

    def __init__(self, *, prompts: PromptsClient, llm: LlmClient) -> None:
        self._prompts = prompts
        self._llm = llm

    def migration_subagents(self, toolset: MigrationToolset) -> list[SubAgent]:
        coder = self._spec(
            CODER_NAME,
            CODER_DESCRIPTION,
            PromptId.CODER,
            AgentRole.CODER,
            toolset.coder,
            toolset.guards,
        )
        coder["skills"] = [CODER_SKILLS_SOURCE]
        return [
            self._spec(
                API_ANALYST_NAME,
                API_ANALYST_DESCRIPTION,
                PromptId.API_ANALYST,
                AgentRole.ANALYST,
                toolset.analyst,
                toolset.guards,
            ),
            self._spec(
                API_SCIENTIST_NAME,
                API_SCIENTIST_DESCRIPTION,
                PromptId.API_SCIENTIST,
                AgentRole.SCIENTIST,
                toolset.scientist,
                toolset.guards,
            ),
            coder,
        ]

    def skill_files(self) -> list[tuple[str, bytes]]:
        skills_root = files(VENDORED_SKILLS_PACKAGE) / VENDORED_SKILLS_DIR
        return [
            (f"{CODER_SKILLS_SOURCE}{relative_path}", skill_file.read_bytes())
            for relative_path, skill_file in _walk_files(skills_root)
        ]

    def _spec(
        self,
        name: str,
        description: str,
        prompt_id: PromptId,
        role: AgentRole,
        tools: Sequence[BaseTool],
        guards: list[AgentMiddleware],
    ) -> SubAgent:
        return {
            "name": name,
            "description": description,
            "system_prompt": self._prompts.get_text(prompt_id),
            "model": self._llm.chat_model_for(role),
            "tools": list(tools),
            "middleware": [TodoListMiddleware(), *guards],
            "response_format": ProviderStrategy(self._prompts.get_schema(prompt_id)),
        }


def _walk_files(root: Traversable) -> list[tuple[str, Traversable]]:
    found_files: list[tuple[str, Traversable]] = []
    pending_dirs: list[tuple[str, Traversable]] = [("", root)]
    while pending_dirs:
        prefix, directory = pending_dirs.pop()
        for entry in directory.iterdir():
            relative_path = f"{prefix}{entry.name}"
            if entry.is_dir():
                pending_dirs.append((f"{relative_path}/", entry))
            else:
                found_files.append((relative_path, entry))
    return found_files
