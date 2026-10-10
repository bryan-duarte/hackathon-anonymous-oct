from dataclasses import dataclass
from enum import StrEnum

from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class MigrationRunContext:
    job_id: str
    base_url: str
    service_key_ref: str
    sandbox_id: str


@dataclass(frozen=True)
class MigrationToolset:
    orchestrator: list[BaseTool]
    analyst: list[BaseTool]
    scientist: list[BaseTool]
    coder: list[BaseTool]
    guards: list[AgentMiddleware]


class SuiteTarget(StrEnum):
    LEGACY = "legacy"
    CANDIDATE = "candidate"
