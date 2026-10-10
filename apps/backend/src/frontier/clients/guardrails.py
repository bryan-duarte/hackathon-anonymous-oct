from typing import TYPE_CHECKING

from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict

if TYPE_CHECKING:
    from frontier.modules.guardrails import GuardrailsService


class GuardrailsClient:
    def __init__(self, service: "GuardrailsService") -> None:
        self._service = service

    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        return await self._service.check(request)
