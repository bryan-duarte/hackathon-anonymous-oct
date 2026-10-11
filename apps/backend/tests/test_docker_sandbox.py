import subprocess
from pathlib import Path

import pytest
from deepagents.backends.protocol import FILE_NOT_FOUND, INVALID_PATH
from pydantic import SecretStr

from frontier.contracts.sandbox import CreateSandboxRequest, ExecRequest, ExportWorkspaceRequest
from frontier.contracts.secrets import ResolvedSecret, ResolveSecretRequest
from frontier.modules.sandbox import DockerDriver, SandboxService

DOCKER_PROBE_TIMEOUT_S = 10
SANDBOX_IMAGE = "python:3.13"
SESSION_TIMEOUT_S = 120
COMMAND_TIMEOUT_S = 30
SERVICE_KEY_REF = "secret-ref-1"
SERVICE_KEY_VALUE = "s3cret-value"
WORKSPACE = "/vercel/sandbox/migration"
TIMED_OUT_EXIT_CODE = 124


def _docker_is_reachable() -> bool:
    try:
        docker_info = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=DOCKER_PROBE_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return docker_info.returncode == 0


pytestmark = pytest.mark.skipif(not _docker_is_reachable(), reason="Docker daemon not reachable")


class _FakeSecrets:
    async def resolve(self, request: ResolveSecretRequest) -> ResolvedSecret:
        return ResolvedSecret(ref=request.ref, value=SecretStr(SERVICE_KEY_VALUE))


def _sandbox_service() -> SandboxService:
    return SandboxService(
        driver=DockerDriver(image=SANDBOX_IMAGE, command_timeout_s=COMMAND_TIMEOUT_S),
        timeout_s=SESSION_TIMEOUT_S,
        job_timeout_s=SESSION_TIMEOUT_S,
        secrets=_FakeSecrets(),
    )


def _container_exists(container_id: str) -> bool:
    listing = subprocess.run(
        ["docker", "ps", "--all", "--quiet", "--no-trunc", "--filter", f"id={container_id}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(listing.stdout.strip())


@pytest.mark.asyncio
async def test_exec_injects_secret_env_and_honours_cwd() -> None:
    service = _sandbox_service()
    async with service.job_session(CreateSandboxRequest(job_id="job-env")) as job_sandbox:
        command_run = await service.exec(
            ExecRequest(
                sandbox_id=job_sandbox.sandbox_id,
                command='printf "%s:%s" "$SERVICE_KEY" "$(pwd)"',
                cwd="/tmp",
                env_secret_refs={"SERVICE_KEY": SERVICE_KEY_REF},
            )
        )

    assert command_run.exit_code == 0
    assert command_run.stdout == f"{SERVICE_KEY_VALUE}:/tmp"


@pytest.mark.asyncio
async def test_exec_returns_timeout_exit_code_when_command_overruns() -> None:
    service = _sandbox_service()
    async with service.job_session(CreateSandboxRequest(job_id="job-timeout")) as job_sandbox:
        command_run = await service.exec(
            ExecRequest(sandbox_id=job_sandbox.sandbox_id, command="sleep 10", timeout_s=1)
        )

    assert command_run.exit_code == TIMED_OUT_EXIT_CODE


@pytest.mark.asyncio
async def test_backend_executes_and_transfers_files_under_the_vercel_workspace_path() -> None:
    async with _sandbox_service().session() as backend:
        execution = backend.execute("echo out; echo err >&2; exit 3")
        uploads = backend.upload_files([(f"{WORKSPACE}/notes.txt", b"hello")])
        downloads = backend.download_files(
            [f"{WORKSPACE}/notes.txt", f"{WORKSPACE}/missing.txt", "relative.txt"]
        )

    assert execution.exit_code == 3
    assert execution.output == "out\n\n<stderr>err</stderr>"
    assert [upload.error for upload in uploads] == [None]
    assert downloads[0].content == b"hello"
    assert downloads[1].error == FILE_NOT_FOUND
    assert downloads[2].error == INVALID_PATH


@pytest.mark.asyncio
async def test_export_copies_workspace_without_excluded_dirs(tmp_path: Path) -> None:
    service = _sandbox_service()
    async with service.job_session(CreateSandboxRequest(job_id="job-export")) as job_sandbox:
        job_sandbox.backend.upload_files(
            [
                (f"{WORKSPACE}/reports/summary.md", b"# summary"),
                (f"{WORKSPACE}/service/.venv/lib/site.py", b"ignored"),
            ]
        )
        exported = await service.export(
            ExportWorkspaceRequest(
                sandbox_id=job_sandbox.sandbox_id,
                source_dir=WORKSPACE,
                destination_dir=str(tmp_path),
            )
        )

    assert exported.file_count == 1
    assert (tmp_path / "reports/summary.md").read_bytes() == b"# summary"
    assert not (tmp_path / "service/.venv").exists()


@pytest.mark.asyncio
async def test_container_is_removed_when_the_session_ends() -> None:
    async with _sandbox_service().session() as backend:
        container_id = backend.id
        assert _container_exists(container_id)

    assert not _container_exists(container_id)
