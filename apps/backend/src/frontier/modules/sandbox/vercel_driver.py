import asyncio
from datetime import timedelta

from langchain_vercel_sandbox import VercelSandbox
from pydantic import SecretStr
from vercel.sandbox import Command, Sandbox

from frontier.contracts.sandbox import ExecResult
from frontier.core.logging_config import get_logger

logger = get_logger(__name__)

AGENT_NETWORK_POLICY = "allow-all"
TIMED_OUT_EXIT_CODE = 124
OUTPUT_UNAVAILABLE = "<output unavailable: failed to fetch command logs>"


class VercelRunningSandbox:
    def __init__(self, sandbox: Sandbox, *, command_timeout_s: int) -> None:
        self._sandbox = sandbox
        self._backend = VercelSandbox(sandbox=sandbox, timeout=command_timeout_s)

    @property
    def sandbox_id(self) -> str:
        return self._sandbox.sandbox_id

    @property
    def backend(self) -> VercelSandbox:
        return self._backend

    async def run(
        self, command: str, *, cwd: str | None, env: dict[str, str], timeout_s: int
    ) -> ExecResult:
        running = await asyncio.to_thread(
            self._sandbox.run_command_detached, "bash", ["-lc", command], cwd=cwd, env=env
        )
        try:
            finished = await asyncio.wait_for(asyncio.to_thread(running.wait), timeout=timeout_s)
        except TimeoutError:
            await _kill(running)
            logger.warning(
                "sandbox_exec_timed_out", sandbox_id=self.sandbox_id, timeout_s=timeout_s
            )
            return ExecResult(
                exit_code=TIMED_OUT_EXIT_CODE, stdout="", stderr=f"timed out after {timeout_s}s"
            )

        try:
            stdout = await asyncio.to_thread(finished.stdout)
            stderr = await asyncio.to_thread(finished.stderr)
        except Exception:
            logger.exception("sandbox_exec_output_unavailable", sandbox_id=self.sandbox_id)
            return ExecResult(exit_code=finished.exit_code, stdout="", stderr=OUTPUT_UNAVAILABLE)
        return ExecResult(exit_code=finished.exit_code, stdout=stdout or "", stderr=stderr or "")

    async def stop(self) -> None:
        await _shut_down(self._sandbox)


class VercelDriver:
    def __init__(
        self,
        *,
        token: SecretStr,
        team_id: str,
        project_id: str,
        runtime: str,
        command_timeout_s: int,
    ) -> None:
        self._token = token
        self._team_id = team_id
        self._project_id = project_id
        self._runtime = runtime
        self._command_timeout_s = command_timeout_s

    async def start(self, *, timeout_s: int) -> VercelRunningSandbox:
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
        return VercelRunningSandbox(sandbox, command_timeout_s=self._command_timeout_s)


async def _kill(running: Command) -> None:
    try:
        await asyncio.to_thread(running.kill)
    except Exception:
        logger.exception("sandbox_exec_kill_failed", sandbox_id=running.sandbox_id)


async def _shut_down(sandbox: Sandbox) -> None:
    try:
        await asyncio.to_thread(sandbox.stop)
        logger.info("sandbox_stopped", sandbox_id=sandbox.sandbox_id)
    except Exception:
        logger.exception("sandbox_stop_failed", sandbox_id=sandbox.sandbox_id)
    finally:
        sandbox.client.close()
