from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict

# Shorter values would match ordinary text and produce false positives.
MIN_SCAN_LENGTH = 8


class GuardrailsService:
    """Screens a migration request before any infrastructure or storage is touched."""

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        reasons = [
            f"context contains the submitted {name}"
            for name, secret in request.secrets.items()
            if len(value := secret.get_secret_value()) >= MIN_SCAN_LENGTH
            and value in request.context
        ]
        return GuardrailVerdict(allowed=not reasons, reasons=reasons)
