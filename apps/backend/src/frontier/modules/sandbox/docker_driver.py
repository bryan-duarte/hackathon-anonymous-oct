import asyncio
import re
import subprocess
import tempfile

from deepagents.backends.protocol import (
    FILE_NOT_FOUND,
    INVALID_PATH,
    IS_DIRECTORY,
    PERMISSION_DENIED,
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from frontier.contracts.sandbox import ExecResult
from frontier.core.logging_config import get_logger
from frontier.modules.sandbox.errors import InvalidSandboxEnvError, SandboxStartError

logger = get_logger(__name__)

SANDBOX_WORKDIR = "/vercel/sandbox"
SANDBOX_LABEL = "frontier.sandbox=1"
TIMED_OUT_EXIT_CODE = 124
NO_TIMEOUT = 0
KILL_GRACE_S = 5
CLIENT_TIMEOUT_MARGIN_S = 15
DOCKER_START_TIMEOUT_S = 300
DOCKER_FILE_TRANSFER_TIMEOUT_S = 120
DOCKER_STOP_TIMEOUT_S = 60
MAX_OUTPUT_CHARS = 100_000
ENV_FILE_PREFIX = "frontier-sandbox-env-"
ENV_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
WRITE_STDIN_TO_PATH_SCRIPT = 'mkdir -p "$(dirname "$1")" && cat > "$1"'
FILE_ERRORS_BY_STDERR_MARKER = (
    ("no such file", FILE_NOT_FOUND),
    ("is a directory", IS_DIRECTORY),
    ("permission denied", PERMISSION_DENIED),
)


class DockerSandbox(BaseSandbox):
    def __init__(self, *, container_id: str, command_timeout_s: int) -> None:
        self._container_id = container_id
        self._command_timeout_s = command_timeout_s

    @property
    def id(self) -> str:
        return self._container_id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        timeout_s = self._command_timeout_s if timeout is None else timeout
        shell_run = _exec_shell(self._container_id, command, cwd=None, env={}, timeout_s=timeout_s)
        output = shell_run.stdout
        if shell_run.stderr.strip():
            output += f"\n<stderr>{shell_run.stderr.strip()}</stderr>"
        output_is_too_long = len(output) > MAX_OUTPUT_CHARS
        if output_is_too_long:
            output = (
                f"{output[:MAX_OUTPUT_CHARS]}\n\n... Output truncated at {MAX_OUTPUT_CHARS} bytes."
            )
        return ExecuteResponse(
            output=output, exit_code=shell_run.exit_code, truncated=output_is_too_long
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return [self._upload_file(path, content) for path, content in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [self._download_file(path) for path in paths]

    def _upload_file(self, path: str, content: bytes) -> FileUploadResponse:
        if not path.startswith("/"):
            return FileUploadResponse(path=path, error=INVALID_PATH)
        try:
            upload = _docker(
                [
                    "exec",
                    "-i",
                    self._container_id,
                    "sh",
                    "-c",
                    WRITE_STDIN_TO_PATH_SCRIPT,
                    "sh",
                    path,
                ],
                stdin=content,
                timeout_s=DOCKER_FILE_TRANSFER_TIMEOUT_S,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return FileUploadResponse(path=path, error=str(error))
        if upload.returncode != 0:
            return FileUploadResponse(path=path, error=_file_error(upload.stderr))
        return FileUploadResponse(path=path)

    def _download_file(self, path: str) -> FileDownloadResponse:
        if not path.startswith("/"):
            return FileDownloadResponse(path=path, error=INVALID_PATH)
        try:
            download = _docker(
                ["exec", self._container_id, "cat", "--", path],
                timeout_s=DOCKER_FILE_TRANSFER_TIMEOUT_S,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return FileDownloadResponse(path=path, error=str(error))
        if download.returncode != 0:
            return FileDownloadResponse(path=path, error=_file_error(download.stderr))
        return FileDownloadResponse(path=path, content=download.stdout)


class DockerRunningSandbox:
    def __init__(self, *, container_id: str, command_timeout_s: int) -> None:
        self._container_id = container_id
        self._backend = DockerSandbox(
            container_id=container_id, command_timeout_s=command_timeout_s
        )

    @property
    def sandbox_id(self) -> str:
        return self._container_id

    @property
    def backend(self) -> DockerSandbox:
        return self._backend

    async def run(
        self, command: str, *, cwd: str | None, env: dict[str, str], timeout_s: int
    ) -> ExecResult:
        shell_run = await asyncio.to_thread(
            _exec_shell, self._container_id, command, cwd=cwd, env=env, timeout_s=timeout_s
        )
        if shell_run.exit_code == TIMED_OUT_EXIT_CODE:
            logger.warning(
                "sandbox_exec_timed_out", sandbox_id=self._container_id, timeout_s=timeout_s
            )
        return shell_run

    async def stop(self) -> None:
        try:
            removal = await asyncio.to_thread(
                _docker, ["rm", "-f", self._container_id], timeout_s=DOCKER_STOP_TIMEOUT_S
            )
        except Exception:
            logger.exception("sandbox_stop_failed", sandbox_id=self._container_id)
            return
        if removal.returncode != 0:
            logger.warning(
                "sandbox_stop_failed",
                sandbox_id=self._container_id,
                stderr=_decode(removal.stderr),
            )
            return
        logger.info("sandbox_stopped", sandbox_id=self._container_id)


class DockerDriver:
    def __init__(self, *, image: str, command_timeout_s: int) -> None:
        self._image = image
        self._command_timeout_s = command_timeout_s

    async def start(self, *, timeout_s: int) -> DockerRunningSandbox:
        container_start = await asyncio.to_thread(
            _docker,
            [
                "run",
                "--detach",
                "--rm",
                "--label",
                SANDBOX_LABEL,
                "--workdir",
                SANDBOX_WORKDIR,
                self._image,
                "sleep",
                str(timeout_s),
            ],
            timeout_s=DOCKER_START_TIMEOUT_S,
        )
        if container_start.returncode != 0:
            raise SandboxStartError(_decode(container_start.stderr))
        container_id = _decode(container_start.stdout).strip()
        logger.info("sandbox_created", sandbox_id=container_id, image=self._image)
        return DockerRunningSandbox(
            container_id=container_id, command_timeout_s=self._command_timeout_s
        )


def _exec_shell(
    container_id: str, command: str, *, cwd: str | None, env: dict[str, str], timeout_s: int
) -> ExecResult:
    cwd_flags = ["--workdir", cwd] if cwd else []
    in_container_deadline = ["timeout", "--kill-after", str(KILL_GRACE_S), str(timeout_s)]
    client_timeout_s = (
        None if timeout_s == NO_TIMEOUT else timeout_s + KILL_GRACE_S + CLIENT_TIMEOUT_MARGIN_S
    )
    # Secret values go through a private (0600) env file that is deleted right after the
    # exec: never through argv (visible in `ps`) nor the docker client's own environment.
    with tempfile.NamedTemporaryFile("w", prefix=ENV_FILE_PREFIX) as env_file:
        env_file.write(_env_file_content(env))
        env_file.flush()
        try:
            completed = _docker(
                [
                    "exec",
                    *cwd_flags,
                    "--env-file",
                    env_file.name,
                    container_id,
                    *in_container_deadline,
                    "bash",
                    "-lc",
                    command,
                ],
                timeout_s=client_timeout_s,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(
                exit_code=TIMED_OUT_EXIT_CODE, stdout="", stderr=f"timed out after {timeout_s}s"
            )
    return ExecResult(
        exit_code=completed.returncode,
        stdout=_decode(completed.stdout),
        stderr=_decode(completed.stderr),
    )


def _env_file_content(env: dict[str, str]) -> str:
    for env_name, env_value in env.items():
        env_entry_is_unsafe = not ENV_NAME_PATTERN.fullmatch(env_name) or "\n" in env_value
        if env_entry_is_unsafe:
            raise InvalidSandboxEnvError(env_name)
    return "".join(f"{env_name}={env_value}\n" for env_name, env_value in env.items())


def _docker(
    arguments: list[str], *, timeout_s: int | None, stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["docker", *arguments],
        input=stdin,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )


def _file_error(stderr: bytes) -> str:
    message = _decode(stderr).strip()
    lowered_message = message.lower()
    return next(
        (error for marker, error in FILE_ERRORS_BY_STDERR_MARKER if marker in lowered_message),
        message or FILE_NOT_FOUND,
    )


def _decode(output: bytes) -> str:
    return output.decode(errors="replace")
