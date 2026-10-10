from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict


class GuardrailsService:
    """Screens a migration request before any infrastructure or storage is touched."""

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        scanned_fields = {"base_url": request.base_url, "context": request.context}
        reasons = [
            f"{field_name} contains the submitted {secret_name}"
            for field_name, field_text in scanned_fields.items()
            for secret_name, secret in request.secrets.items()
            if secret.get_secret_value() in field_text
        ]
        return GuardrailVerdict(allowed=not reasons, reasons=reasons)
