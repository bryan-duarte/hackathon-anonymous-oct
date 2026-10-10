from frontier.contracts.sandbox import (
    CreateSandboxRequest,
    DestroySandboxRequest,
    ExecRequest,
    ExecResult,
    SandboxDestroyed,
    SandboxHandle,
)


class SandboxService:
    """Isolated code execution. Secret handles are resolved into env vars server-side."""

    async def create(self, request: CreateSandboxRequest) -> SandboxHandle:
        raise NotImplementedError("sandbox.create")

    async def exec(self, request: ExecRequest) -> ExecResult:
        raise NotImplementedError("sandbox.exec")

    async def destroy(self, request: DestroySandboxRequest) -> SandboxDestroyed:
        raise NotImplementedError("sandbox.destroy")
