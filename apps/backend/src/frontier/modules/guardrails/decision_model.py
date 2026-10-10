import httpx
from pydantic import SecretStr, ValidationError

from frontier.core.logging_config import get_logger
from frontier.modules.guardrails.errors import GuardrailUnavailableError
from frontier.modules.guardrails.schemas import (
    DecisionsRequest,
    DecisionsResponse,
    ScreeningState,
    YesNoQuestion,
)

CONNECT_RETRIES = 2

logger = get_logger(__name__)


class DecisionModel:
    """Typed yes/no classifier served by the OpenRouter Decisions API (TypeSafe Jev)."""

    def __init__(
        self,
        api_key: SecretStr,
        url: str,
        model: str,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._url = url
        self._model = model
        self._timeout_s = timeout_s
        self._transport = transport

    async def answer_yes_no(
        self, state: ScreeningState, questions: dict[str, YesNoQuestion]
    ) -> dict[str, float]:
        decisions_request = DecisionsRequest(model=self._model, state=state, questions=questions)
        decisions = await self._submit(decisions_request)
        missing_answers = questions.keys() - decisions.answers.keys()
        if missing_answers:
            logger.warning("guardrail_decision_incomplete", missing=sorted(missing_answers))
            raise GuardrailUnavailableError("response is missing answers")
        return {question_id: decisions.answers[question_id].noul for question_id in questions}

    async def _submit(self, decisions_request: DecisionsRequest) -> DecisionsResponse:
        transport = self._transport or httpx.AsyncHTTPTransport(retries=CONNECT_RETRIES)
        try:
            async with httpx.AsyncClient(transport=transport, timeout=self._timeout_s) as http:
                response = await http.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json=decisions_request.model_dump(mode="json", exclude_none=True),
                )
            response.raise_for_status()
            return DecisionsResponse.model_validate_json(response.content)
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            logger.warning("guardrail_decision_rejected", status_code=status_code)
            raise GuardrailUnavailableError(f"HTTP {status_code}") from error
        except httpx.HTTPError as error:
            logger.warning("guardrail_decision_unreachable", error_type=type(error).__name__)
            raise GuardrailUnavailableError(type(error).__name__) from error
        except ValidationError as error:
            logger.warning("guardrail_decision_malformed", error_count=error.error_count())
            raise GuardrailUnavailableError("malformed response") from error
