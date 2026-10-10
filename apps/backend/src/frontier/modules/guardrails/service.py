import asyncio
import re

from pydantic import SecretStr

from frontier.contracts.guardrails import (
    GuardrailCheckRequest,
    GuardrailVerdict,
    GuardrailViolation,
    GuardrailViolationCode,
)
from frontier.core.logging_config import get_logger
from frontier.modules.guardrails.decision_model import DecisionModel
from frontier.modules.guardrails.policy import (
    PLATFORM_TASK,
    RISK_POLICIES,
    exposed_secret_violation,
)
from frontier.modules.guardrails.schemas import RiskPolicy, ScreeningState, SecretMatch
from frontier.modules.guardrails.secret_patterns import find_secrets

REDACTION_MARKER = "[REDACTED]"
CHUNK_OVERLAP_CHARS = 500

RiskScores = dict[GuardrailViolationCode, float]

logger = get_logger(__name__)


class GuardrailsService:
    """Screens a migration request before any infrastructure or storage is touched."""

    def __init__(
        self, decision_model: DecisionModel, block_threshold: float, chunk_chars: int
    ) -> None:
        self._decision_model = decision_model
        self._block_threshold = block_threshold
        self._chunk_chars = chunk_chars

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        base_url_secrets = _find_exposed_secrets(request.base_url or "", request.secrets)
        context_secrets = _find_exposed_secrets(request.context, request.secrets)
        secret_violations = _secret_violations(base_url_secrets + context_secrets)

        redacted_base_url = (
            _redact(request.base_url, base_url_secrets) if request.base_url else None
        )
        risk_scores = await self._score_risks(
            base_url=redacted_base_url, context=_redact(request.context, context_secrets)
        )
        risk_violations = [
            policy.violation
            for policy in RISK_POLICIES
            if self._should_report(
                policy, risk_scores, has_secret_violations=bool(secret_violations)
            )
        ]

        violations = secret_violations + risk_violations
        logger.info(
            "guardrail_checked",
            allowed=not violations,
            violation_codes=[violation.code.value for violation in violations],
            risk_scores={code.value: score for code, score in risk_scores.items()},
        )
        return GuardrailVerdict(allowed=not violations, violations=violations)

    async def _score_risks(self, base_url: str | None, context: str) -> RiskScores:
        questions = {policy.code.value: policy.question for policy in RISK_POLICIES}
        chunk_scores = await asyncio.gather(
            *(
                self._decision_model.answer_yes_no(
                    ScreeningState(task=PLATFORM_TASK, base_url=base_url, context=chunk),
                    questions,
                )
                for chunk in _split_into_chunks(context, self._chunk_chars)
            )
        )
        return {
            policy.code: max(scores[policy.code.value] for scores in chunk_scores)
            for policy in RISK_POLICIES
        }

    def _should_report(
        self, policy: RiskPolicy, risk_scores: RiskScores, has_secret_violations: bool
    ) -> bool:
        exceeds_block_threshold = risk_scores[policy.code] >= self._block_threshold
        secret_already_reported = (
            policy.code == GuardrailViolationCode.EXPOSED_SECRET and has_secret_violations
        )
        return exceeds_block_threshold and not secret_already_reported


def _find_exposed_secrets(text: str, submitted_secrets: dict[str, SecretStr]) -> list[SecretMatch]:
    submitted_secret_matches = [
        SecretMatch(label=f"your {secret_name} value", start=match.start(), end=match.end())
        for secret_name, secret in submitted_secrets.items()
        for match in re.finditer(re.escape(secret.get_secret_value()), text)
    ]
    return submitted_secret_matches + find_secrets(text)


def _secret_violations(secret_matches: list[SecretMatch]) -> list[GuardrailViolation]:
    unique_secret_labels = dict.fromkeys(match.label for match in secret_matches)
    return [exposed_secret_violation(label) for label in unique_secret_labels]


def _redact(text: str, secret_matches: list[SecretMatch]) -> str:
    redacted_parts: list[str] = []
    cursor = 0
    for match in sorted(secret_matches, key=lambda secret_match: secret_match.start):
        starts_after_previous_redaction = match.start >= cursor
        if starts_after_previous_redaction:
            redacted_parts += [text[cursor : match.start], REDACTION_MARKER]
        cursor = max(cursor, match.end)
    redacted_parts.append(text[cursor:])
    return "".join(redacted_parts)


def _split_into_chunks(text: str, chunk_chars: int) -> list[str]:
    chunk_step = chunk_chars - CHUNK_OVERLAP_CHARS
    chunk_start_limit = max(len(text) - CHUNK_OVERLAP_CHARS, 1)
    return [text[start : start + chunk_chars] for start in range(0, chunk_start_limit, chunk_step)]
