from typing import Protocol

from deepagents.backends.sandbox import BaseSandbox

from frontier.contracts.sandbox import ExecResult


class RunningSandbox(Protocol):
    @property
    def sandbox_id(self) -> str: ...

    @property
    def backend(self) -> BaseSandbox: ...

    async def run(
        self, command: str, *, cwd: str | None, env: dict[str, str], timeout_s: int
    ) -> ExecResult: ...

    async def stop(self) -> None: ...


class SandboxDriver(Protocol):
    async def start(self, *, timeout_s: int) -> RunningSandbox: ...
