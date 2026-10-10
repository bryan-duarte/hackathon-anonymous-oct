from collections.abc import Mapping
from functools import cached_property
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import PrivateAttr, SecretStr

from frontier.contracts.llm import AgentRole
from frontier.modules.llm_gateway.errors import MissingRoleModelsError


class BearerAuthChatAnthropic(ChatAnthropic):
    """Sends Bearer auth (OpenRouter's documented scheme) without exposing the key as a field."""

    _bearer_token: SecretStr = PrivateAttr()

    def __init__(
        self,
        *,
        bearer_token: SecretStr,
        model: str,
        base_url: str,
        max_tokens: int,
        timeout_s: float,
        max_retries: int,
    ) -> None:
        super().__init__(
            api_key=bearer_token,
            model=model,
            base_url=base_url,
            max_tokens=max_tokens,
            timeout=timeout_s,
            max_retries=max_retries,
        )
        self._bearer_token = bearer_token

    @cached_property
    def _client_params(self) -> dict[str, Any]:
        client_params = super()._client_params
        client_params["default_headers"] = {
            **client_params["default_headers"],
            "Authorization": f"Bearer {self._bearer_token.get_secret_value()}",
        }
        return client_params


class LlmGatewayService:
    """LLM access through OpenRouter's Anthropic-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        model: str,
        models_by_role: Mapping[AgentRole, str],
        max_tokens: int,
        timeout_s: float,
        max_retries: int,
    ) -> None:
        missing_roles = set(AgentRole) - models_by_role.keys()
        if missing_roles:
            raise MissingRoleModelsError(missing_roles)

        self._default_model = model
        self._models_by_role = dict(models_by_role)
        self._chat_models: dict[str, BaseChatModel] = {
            model_name: BearerAuthChatAnthropic(
                bearer_token=api_key,
                model=model_name,
                base_url=base_url,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                max_retries=max_retries,
            )
            for model_name in {model, *models_by_role.values()}
        }

    def chat_model(self) -> BaseChatModel:
        return self._chat_models[self._default_model]

    def chat_model_for(self, role: AgentRole) -> BaseChatModel:
        return self._chat_models[self._models_by_role[role]]
