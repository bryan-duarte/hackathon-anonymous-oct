from dataclasses import dataclass

from deepagents.backends.protocol import BackendProtocol
from pydantic import Field

from frontier.contracts._base import StrictModel


class CreateSandboxRequest(StrictModel):
    job_id: str
    env_secret_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Env var name -> secret handle; resolved server-side, never seen by the LLM.",
    )


class SandboxHandle(StrictModel):
    sandbox_id: str


class ExecRequest(StrictModel):
    sandbox_id: str
    command: str
    timeout_s: int = Field(default=120, gt=0)
    cwd: str | None = None
    env_secret_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Env var name -> secret handle, set for this one command only.",
    )


class ExecResult(StrictModel):
    exit_code: int
    stdout: str
    stderr: str


class DestroySandboxRequest(StrictModel):
    sandbox_id: str


class SandboxDestroyed(StrictModel):
    sandbox_id: str


class ExportWorkspaceRequest(StrictModel):
    sandbox_id: str
    source_dir: str
    destination_dir: str


class ExportedWorkspace(StrictModel):
    path: str
    file_count: int


@dataclass(frozen=True)
class JobSandbox:
    sandbox_id: str
    backend: BackendProtocol
