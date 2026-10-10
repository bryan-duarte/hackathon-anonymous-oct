import asyncio
import shlex
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path, PurePosixPath

from deepagents.backends.protocol import BackendProtocol
from langchain_vercel_sandbox import VercelSandbox
from pydantic import SecretStr
from vercel.sandbox import Command, Sandbox

from frontier.clients.secrets import SecretsClient
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
from frontier.contracts.secrets import ResolveSecretRequest
from frontier.core.logging_config import get_logger
from frontier.modules.sandbox.errors import UnknownSandboxError, WorkspaceListingError

logger = get_logger(__name__)

AGENT_NETWORK_POLICY = "allow-all"
SUCCESS_EXIT_CODE = 0
TIMED_OUT_EXIT_CODE = 124
OUTPUT_UNAVAILABLE = "<output unavailable: failed to fetch command logs>"
EXPORT_EXCLUDED_DIRS = (
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
)
EXPORT_LISTING_TIMEOUT_S = 60
FIND_PATH_SEPARATOR = "\0"


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
        job_timeout_s: int,
        command_timeout_s: int,
        secrets: SecretsClient,
    ) -> None:
        self._token = token
        self._team_id = team_id
        self._project_id = project_id
        self._runtime = runtime
        self._timeout_s = timeout_s
        self._job_timeout_s = job_timeout_s
        self._command_timeout_s = command_timeout_s
        self._secrets = secrets
        self._live_sandboxes: dict[str, Sandbox] = {}

    @asynccontextmanager
    async def session(self) -> AsyncIterator[BackendProtocol]:
        sandbox = await self._create_sandbox(timeout_s=self._timeout_s)
        try:
            yield VercelSandbox(sandbox=sandbox, timeout=self._command_timeout_s)
        finally:
            await _shut_down(sandbox)

    @asynccontextmanager
    async def job_session(self, request: CreateSandboxRequest) -> AsyncIterator[JobSandbox]:
        sandbox = await self._create_sandbox(timeout_s=self._job_timeout_s)
        self._live_sandboxes[sandbox.sandbox_id] = sandbox
        logger.info("job_sandbox_opened", job_id=request.job_id, sandbox_id=sandbox.sandbox_id)
        try:
            yield JobSandbox(
                sandbox_id=sandbox.sandbox_id,
                backend=VercelSandbox(sandbox=sandbox, timeout=self._command_timeout_s),
            )
        finally:
            self._live_sandboxes.pop(sandbox.sandbox_id, None)
            await _shut_down(sandbox)

    async def _create_sandbox(self, *, timeout_s: int) -> Sandbox:
        # The vercel 0.5.9 SDK is synchronous, and a worker thread cannot be cancelled: if the
        # caller is cancelled mid-create, wait for the sandbox anyway so it can be stopped.
        sandbox_creation = asyncio.ensure_future(
            asyncio.to_thread(
                Sandbox.create,
                runtime=self._runtime,
                timeout=timedelta(seconds=timeout_s),
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
        sandbox = self._live_sandbox(request.sandbox_id)
        env = await self._resolve_env(request.env_secret_refs)
        return await _run_shell(
            sandbox, request.command, cwd=request.cwd, env=env, timeout_s=request.timeout_s
        )

    async def export(self, request: ExportWorkspaceRequest) -> ExportedWorkspace:
        sandbox = self._live_sandbox(request.sandbox_id)
        listing = await _run_shell(
            sandbox,
            _list_workspace_files_command(request.source_dir),
            cwd=None,
            env={},
            timeout_s=EXPORT_LISTING_TIMEOUT_S,
        )
        listing_failed = listing.exit_code != SUCCESS_EXIT_CODE
        if listing_failed:
            raise WorkspaceListingError(request.sandbox_id, listing.stderr)

        sandbox_paths = [path for path in listing.stdout.split(FIND_PATH_SEPARATOR) if path]
        downloads = await asyncio.to_thread(
            VercelSandbox(sandbox=sandbox).download_files, sandbox_paths
        )
        destination_dir = Path(request.destination_dir)
        written_count = 0
        for download in downloads:
            if download.content is None:
                logger.warning(
                    "sandbox_export_file_failed", path=download.path, error=download.error
                )
                continue
            relative_path = PurePosixPath(download.path).relative_to(request.source_dir)
            await asyncio.to_thread(_write_file, destination_dir / relative_path, download.content)
            written_count += 1

        logger.info(
            "sandbox_workspace_exported", sandbox_id=request.sandbox_id, file_count=written_count
        )
        return ExportedWorkspace(path=str(destination_dir), file_count=written_count)

    async def destroy(self, request: DestroySandboxRequest) -> SandboxDestroyed:
        raise NotImplementedError("sandbox.destroy")

    def _live_sandbox(self, sandbox_id: str) -> Sandbox:
        sandbox = self._live_sandboxes.get(sandbox_id)
        if sandbox is None:
            raise UnknownSandboxError(sandbox_id)
        return sandbox

    async def _resolve_env(self, env_secret_refs: Mapping[str, str]) -> dict[str, str]:
        env: dict[str, str] = {}
        for env_name, secret_ref in env_secret_refs.items():
            resolved = await self._secrets.resolve(ResolveSecretRequest(ref=secret_ref))
            env[env_name] = resolved.value.get_secret_value()
        return env


async def _run_shell(
    sandbox: Sandbox, command: str, *, cwd: str | None, env: dict[str, str], timeout_s: int
) -> ExecResult:
    running = await asyncio.to_thread(
        sandbox.run_command_detached, "bash", ["-lc", command], cwd=cwd, env=env
    )
    try:
        finished = await asyncio.wait_for(asyncio.to_thread(running.wait), timeout=timeout_s)
    except TimeoutError:
        await _kill(running)
        logger.warning("sandbox_exec_timed_out", sandbox_id=sandbox.sandbox_id, timeout_s=timeout_s)
        return ExecResult(
            exit_code=TIMED_OUT_EXIT_CODE, stdout="", stderr=f"timed out after {timeout_s}s"
        )

    try:
        stdout = await asyncio.to_thread(finished.stdout)
        stderr = await asyncio.to_thread(finished.stderr)
    except Exception:
        logger.exception("sandbox_exec_output_unavailable", sandbox_id=sandbox.sandbox_id)
        return ExecResult(exit_code=finished.exit_code, stdout="", stderr=OUTPUT_UNAVAILABLE)
    return ExecResult(exit_code=finished.exit_code, stdout=stdout or "", stderr=stderr or "")


async def _kill(running: Command) -> None:
    try:
        await asyncio.to_thread(running.kill)
    except Exception:
        logger.exception("sandbox_exec_kill_failed", sandbox_id=running.sandbox_id)


def _list_workspace_files_command(source_dir: str) -> str:
    quoted_source_dir = shlex.quote(source_dir)
    pruned_dirs = " -o ".join(f"-name {shlex.quote(name)}" for name in EXPORT_EXCLUDED_DIRS)
    return (
        f"test -d {quoted_source_dir} || exit 0; "
        f"find {quoted_source_dir} -type d \\( {pruned_dirs} \\) -prune -o -type f -print0"
    )


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


async def _shut_down(sandbox: Sandbox) -> None:
    try:
        await asyncio.to_thread(sandbox.stop)
        logger.info("sandbox_stopped", sandbox_id=sandbox.sandbox_id)
    except Exception:
        logger.exception("sandbox_stop_failed", sandbox_id=sandbox.sandbox_id)
    finally:
        sandbox.client.close()
