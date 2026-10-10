import json
import re
import shlex
from collections import Counter

from langchain.tools import ToolRuntime
from pydantic import ValidationError

from frontier.clients.sandbox import SandboxClient
from frontier.clients.secrets import SecretsClient
from frontier.contracts.sandbox import ExecRequest, ExecResult
from frontier.contracts.tools import MigrationRunContext, SuiteTarget
from frontier.contracts.workspace import (
    BEHAVIORS_CATALOGUE_PATH,
    CHARACTERIZATION_DIR,
    SERVICE_DIR,
    SERVICE_KEY_ENV,
    TARGET_BASE_URL_ENV,
)
from frontier.modules.tools.redaction import redact_for_run
from frontier.modules.tools.schemas import BehaviorCatalogue

SUITE_TIMEOUT_S = 900
WORKSPACE_READ_TIMEOUT_S = 60
CANDIDATE_STARTUP_TIMEOUT_S = 30
CANDIDATE_LOG_PATH = "/tmp/candidate.log"
FREE_PORT_COMMAND = (
    'python -c \'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); '
    "print(s.getsockname()[1])'"
)
CANDIDATE_LOG_TAIL_LINES = 80
SUCCESS_EXIT_CODE = 0
STARTUP_FAILED_EXIT_CODE = 3
GREP_NO_MATCH_EXIT_CODE = 1
MAX_SUITE_OUTPUT_CHARS = 12_000
BEHAVIOR_ID_REGEX = re.compile(r"B-\d+")
BEHAVIOR_MARKER_PATTERN = r"behavior\(\s*[\"']B-[0-9]+[\"']"


class CharacterizationRunner:
    """Deterministic gate checks: run the characterization suite and diff behavior coverage."""

    def __init__(self, *, sandbox: SandboxClient, secrets: SecretsClient) -> None:
        self._sandbox = sandbox
        self._secrets = secrets

    async def run_characterization_suite(
        self, target: SuiteTarget, runtime: ToolRuntime[MigrationRunContext]
    ) -> str:
        """Run the characterization suite against the legacy API or the candidate (new version)
        and return the exit code, pass/fail flag and the tail of the pytest output."""
        context = runtime.context
        command = (
            _legacy_suite_command(context.base_url)
            if target == SuiteTarget.LEGACY
            else _candidate_suite_command()
        )
        suite_run = await self._sandbox.exec(
            ExecRequest(
                sandbox_id=context.sandbox_id,
                command=command,
                timeout_s=SUITE_TIMEOUT_S,
                env_secret_refs={SERVICE_KEY_ENV: context.service_key_ref},
            )
        )
        suite_passed = suite_run.exit_code == SUCCESS_EXIT_CODE
        output_tail = f"{suite_run.stderr}\n{suite_run.stdout}"[-MAX_SUITE_OUTPUT_CHARS:]
        report = (
            f"target={target} exit_code={suite_run.exit_code} passed={suite_passed}\n{output_tail}"
        )
        return await redact_for_run(self._secrets, report, context)

    async def check_behavior_coverage(self, runtime: ToolRuntime[MigrationRunContext]) -> str:
        """Compare the behavior IDs in reports/behaviors.json with the
        @pytest.mark.behavior("B-NNN") IDs used in the characterization suite."""
        context = runtime.context
        catalogue_read = await self._read_workspace(
            context, f"cat {shlex.quote(BEHAVIORS_CATALOGUE_PATH)}"
        )
        catalogue_unreadable = catalogue_read.exit_code != SUCCESS_EXIT_CODE
        if catalogue_unreadable:
            return f"invalid_catalogue: cannot read {BEHAVIORS_CATALOGUE_PATH}"
        try:
            catalogue = BehaviorCatalogue.model_validate(json.loads(catalogue_read.stdout))
        except (json.JSONDecodeError, ValidationError) as error:
            return await redact_for_run(self._secrets, f"invalid_catalogue: {error}", context)

        markers_grep = await self._read_workspace(context, _behavior_markers_command())
        grep_failed = markers_grep.exit_code not in (SUCCESS_EXIT_CODE, GREP_NO_MATCH_EXIT_CODE)
        if grep_failed:
            return f"invalid_suite: cannot scan {CHARACTERIZATION_DIR}: {markers_grep.stderr}"

        catalogue_ids = [behavior.id for behavior in catalogue.behaviors]
        tested_ids = set(BEHAVIOR_ID_REGEX.findall(markers_grep.stdout))
        return _coverage_report(catalogue_ids, tested_ids)

    async def _read_workspace(self, context: MigrationRunContext, command: str) -> ExecResult:
        return await self._sandbox.exec(
            ExecRequest(
                sandbox_id=context.sandbox_id, command=command, timeout_s=WORKSPACE_READ_TIMEOUT_S
            )
        )


def _legacy_suite_command(base_url: str) -> str:
    return (
        f"cd {CHARACTERIZATION_DIR} && python -m pip install -q -r requirements.txt && "
        f"{TARGET_BASE_URL_ENV}={shlex.quote(base_url)} python -m pytest -q -rA --tb=short"
    )


def _candidate_suite_command() -> str:
    candidate_is_up = (
        "kill -0 $candidate_pid 2>/dev/null && "
        "(exec 3<>/dev/tcp/127.0.0.1/$candidate_port) 2>/dev/null"
    )
    return f"""\
cd {SERVICE_DIR} && python -m pip install -q -r requirements.txt || exit {STARTUP_FAILED_EXIT_CODE}
candidate_port=$({FREE_PORT_COMMAND})
PORT=$candidate_port setsid bash ./run.sh > {CANDIDATE_LOG_PATH} 2>&1 &
candidate_pid=$!
for _ in $(seq 1 {CANDIDATE_STARTUP_TIMEOUT_S}); do {candidate_is_up} && break; sleep 1; done
if ! {candidate_is_up}; then
  echo startup_failed
  tail -n {CANDIDATE_LOG_TAIL_LINES} {CANDIDATE_LOG_PATH}
  kill -- -$candidate_pid 2>/dev/null
  exit {STARTUP_FAILED_EXIT_CODE}
fi
cd {CHARACTERIZATION_DIR} && python -m pip install -q -r requirements.txt && \
{TARGET_BASE_URL_ENV}=http://127.0.0.1:$candidate_port python -m pytest -q -rA --tb=short
suite_status=$?
kill -- -$candidate_pid 2>/dev/null
exit $suite_status
"""


def _behavior_markers_command() -> str:
    return (
        f"grep -rhoE {shlex.quote(BEHAVIOR_MARKER_PATTERN)} --include='*.py' "
        f"{shlex.quote(CHARACTERIZATION_DIR)}"
    )


def _coverage_report(catalogue_ids: list[str], tested_ids: set[str]) -> str:
    unique_catalogue_ids = set(catalogue_ids)
    duplicated_ids = sorted(
        behavior_id
        for behavior_id, occurrences in Counter(catalogue_ids).items()
        if occurrences > 1
    )
    missing_ids = sorted(unique_catalogue_ids - tested_ids)
    unknown_ids = sorted(tested_ids - unique_catalogue_ids)
    coverage_is_complete = not missing_ids and not unknown_ids and not duplicated_ids
    return (
        f"catalogue_count={len(unique_catalogue_ids)}\n"
        f"covered_count={len(unique_catalogue_ids & tested_ids)}\n"
        f"missing={missing_ids}\n"
        f"unknown={unknown_ids}\n"
        f"duplicated_catalogue_ids={duplicated_ids}\n"
        f"complete={str(coverage_is_complete).lower()}"
    )
