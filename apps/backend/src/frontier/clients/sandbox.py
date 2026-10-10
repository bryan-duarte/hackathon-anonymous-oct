from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from deepagents.backends.protocol import BackendProtocol

from frontier.contracts.sandbox import (
    CreateSandboxRequest,
    DestroySandboxRequest,
    ExecRequest,
    ExecResult,
    ExportedWorkspace,
    ExportWorkspaceRequest,
    JobSandbox,
    SandboxDestroyed,
    SandboxHandle,
)

if TYPE_CHECKING:
    from frontier.modules.sandbox import SandboxService


class SandboxClient:
    def __init__(self, service: "SandboxService") -> None:
        self._service = service

    def session(self) -> AbstractAsyncContextManager[BackendProtocol]:
        return self._service.session()

    def job_session(self, request: CreateSandboxRequest) -> AbstractAsyncContextManager[JobSandbox]:
        return self._service.job_session(request)

    async def create(self, request: CreateSandboxRequest) -> SandboxHandle:
        return await self._service.create(request)

    async def exec(self, request: ExecRequest) -> ExecResult:
        return await self._service.exec(request)

    async def export(self, request: ExportWorkspaceRequest) -> ExportedWorkspace:
        return await self._service.export(request)

    async def destroy(self, request: DestroySandboxRequest) -> SandboxDestroyed:
        return await self._service.destroy(request)
