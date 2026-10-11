import asyncio
import shlex
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from deepagents.backends.protocol import BackendProtocol

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
from frontier.modules.sandbox.base import RunningSandbox, SandboxDriver
from frontier.modules.sandbox.errors import UnknownSandboxError, WorkspaceListingError

logger = get_logger(__name__)

SUCCESS_EXIT_CODE = 0
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
        driver: SandboxDriver,
        timeout_s: int,
        job_timeout_s: int,
        secrets: SecretsClient,
    ) -> None:
        self._driver = driver
        self._timeout_s = timeout_s
        self._job_timeout_s = job_timeout_s
        self._secrets = secrets
        self._live_sandboxes: dict[str, RunningSandbox] = {}

    @asynccontextmanager
    async def session(self) -> AsyncIterator[BackendProtocol]:
        running = await self._driver.start(timeout_s=self._timeout_s)
        try:
            yield running.backend
        finally:
            await running.stop()

    @asynccontextmanager
    async def job_session(self, request: CreateSandboxRequest) -> AsyncIterator[JobSandbox]:
        running = await self._driver.start(timeout_s=self._job_timeout_s)
        self._live_sandboxes[running.sandbox_id] = running
        logger.info("job_sandbox_opened", job_id=request.job_id, sandbox_id=running.sandbox_id)
        try:
            yield JobSandbox(sandbox_id=running.sandbox_id, backend=running.backend)
        finally:
            self._live_sandboxes.pop(running.sandbox_id, None)
            await running.stop()

    async def create(self, request: CreateSandboxRequest) -> SandboxHandle:
        raise NotImplementedError("sandbox.create")

    async def exec(self, request: ExecRequest) -> ExecResult:
        running = self._live_sandbox(request.sandbox_id)
        env = await self._resolve_env(request.env_secret_refs)
        return await running.run(
            request.command, cwd=request.cwd, env=env, timeout_s=request.timeout_s
        )

    async def export(self, request: ExportWorkspaceRequest) -> ExportedWorkspace:
        running = self._live_sandbox(request.sandbox_id)
        listing = await running.run(
            _list_workspace_files_command(request.source_dir),
            cwd=None,
            env={},
            timeout_s=EXPORT_LISTING_TIMEOUT_S,
        )
        listing_failed = listing.exit_code != SUCCESS_EXIT_CODE
        if listing_failed:
            raise WorkspaceListingError(request.sandbox_id, listing.stderr)

        sandbox_paths = [path for path in listing.stdout.split(FIND_PATH_SEPARATOR) if path]
        downloads = await asyncio.to_thread(running.backend.download_files, sandbox_paths)
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

    def _live_sandbox(self, sandbox_id: str) -> RunningSandbox:
        running = self._live_sandboxes.get(sandbox_id)
        if running is None:
            raise UnknownSandboxError(sandbox_id)
        return running

    async def _resolve_env(self, env_secret_refs: Mapping[str, str]) -> dict[str, str]:
        env: dict[str, str] = {}
        for env_name, secret_ref in env_secret_refs.items():
            resolved = await self._secrets.resolve(ResolveSecretRequest(ref=secret_ref))
            env[env_name] = resolved.value.get_secret_value()
        return env


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
