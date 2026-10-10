import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from deepagents.backends.protocol import BackendProtocol
from langchain_vercel_sandbox import VercelSandbox
from pydantic import SecretStr
from vercel.sandbox import Sandbox

from frontier.contracts.sandbox import (
    CreateSandboxRequest,
    DestroySandboxRequest,
    ExecRequest,
    ExecResult,
    SandboxDestroyed,
    SandboxHandle,
)
from frontier.core.logging_config import get_logger

logger = get_logger(__name__)

AGENT_NETWORK_POLICY = "allow-all"


class SandboxService:
    """Isolated code execution. Secret handles are resolved into env vars server-side."""

    def __init__(
        self,
        *,
        token: SecretStr,
        team_id: str,
        project_id: str,
        runtime: str,
        timeout_s: int,
        command_timeout_s: int,
    ) -> None:
        self._token = token
        self._team_id = team_id
        self._project_id = project_id
        self._runtime = runtime
        self._timeout_s = timeout_s
        self._command_timeout_s = command_timeout_s

    @asynccontextmanager
    async def session(self) -> AsyncIterator[BackendProtocol]:
        sandbox = await self._create_sandbox()
        try:
            yield VercelSandbox(sandbox=sandbox, timeout=self._command_timeout_s)
        finally:
            await _shut_down(sandbox)

    async def _create_sandbox(self) -> Sandbox:
        # The vercel 0.5.9 SDK is synchronous, and a worker thread cannot be cancelled: if the
        # caller is cancelled mid-create, wait for the sandbox anyway so it can be stopped.
        sandbox_creation = asyncio.ensure_future(
            asyncio.to_thread(
                Sandbox.create,
                runtime=self._runtime,
                timeout=timedelta(seconds=self._timeout_s),
                network_policy=AGENT_NETWORK_POLICY,
                token=self._token.get_secret_value(),
                team_id=self._team_id,
                project_id=self._project_id,
            )
        )
        try:
            sandbox = await asyncio.shield(sandbox_creation)
        except asyncio.CancelledError:
            await _shut_down(await sandbox_creation)
            raise
        logger.info("sandbox_created", sandbox_id=sandbox.sandbox_id)
        return sandbox

    async def create(self, request: CreateSandboxRequest) -> SandboxHandle:
        raise NotImplementedError("sandbox.create")

    async def exec(self, request: ExecRequest) -> ExecResult:
        raise NotImplementedError("sandbox.exec")

    async def destroy(self, request: DestroySandboxRequest) -> SandboxDestroyed:
        raise NotImplementedError("sandbox.destroy")


async def _shut_down(sandbox: Sandbox) -> None:
    try:
        await asyncio.to_thread(sandbox.stop)
        logger.info("sandbox_stopped", sandbox_id=sandbox.sandbox_id)
    except Exception:
        logger.exception("sandbox_stop_failed", sandbox_id=sandbox.sandbox_id)
    finally:
        sandbox.client.close()
