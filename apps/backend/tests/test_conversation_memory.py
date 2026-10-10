from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import BaseCheckpointSaver

from frontier.clients.sessions import SessionsClient
from frontier.contracts.guardrails import GuardrailCheckRequest, GuardrailVerdict
from frontier.contracts.orchestrator import ChatRequest
from frontier.contracts.prompts import PromptId
from frontier.contracts.sessions import GetHistoryRequest, SessionMessage
from frontier.core.db import open_checkpointer
from frontier.modules.orchestrator import OrchestratorService
from frontier.modules.sessions import SessionsService

TEST_SYSTEM_PROMPT = "You are a test agent."


class _ToolFreeFakeChatModel(GenericFakeChatModel):
    def bind_tools(self, tools: Sequence[object], **kwargs: object) -> "_ToolFreeFakeChatModel":
        return self


class _FakeLlm:
    def __init__(self, scripted_replies: Iterator[AIMessage]) -> None:
        self._model = _ToolFreeFakeChatModel(messages=scripted_replies)

    def chat_model(self) -> _ToolFreeFakeChatModel:
        return self._model


class _FakePrompts:
    def get_text(self, prompt_id: PromptId) -> str:
        return TEST_SYSTEM_PROMPT


class _InMemorySandbox:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[BackendProtocol]:
        yield StateBackend()


class _AllowAllGuardrails:
    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        return GuardrailVerdict(allowed=True, violations=[])


def _orchestrator(
    checkpointer: BaseCheckpointSaver, scripted_replies: list[str]
) -> OrchestratorService:
    return OrchestratorService(
        llm=_FakeLlm(iter(AIMessage(content=reply) for reply in scripted_replies)),
        prompts=_FakePrompts(),
        sandbox=_InMemorySandbox(),
        sessions=SessionsClient(SessionsService(checkpointer)),
        guardrails=_AllowAllGuardrails(),
    )


@pytest.mark.asyncio
async def test_conversation_survives_a_restart(tmp_path: Path) -> None:
    database = tmp_path / "checkpoints.db"
    async with open_checkpointer(database) as checkpointer:
        first_reply = await _orchestrator(checkpointer, ["Hi Bryan"]).chat(
            ChatRequest(message="My name is Bryan")
        )

    async with open_checkpointer(database) as checkpointer:
        restarted_orchestrator = _orchestrator(checkpointer, ["Your name is Bryan"])
        second_reply = await restarted_orchestrator.chat(
            ChatRequest(session_id=first_reply.session_id, message="What is my name?")
        )
        history = await restarted_orchestrator.get_history(
            GetHistoryRequest(session_id=first_reply.session_id)
        )

    assert second_reply.session_id == first_reply.session_id
    assert history is not None
    assert history.messages == [
        SessionMessage(role="user", content="My name is Bryan"),
        SessionMessage(role="assistant", content="Hi Bryan"),
        SessionMessage(role="user", content="What is my name?"),
        SessionMessage(role="assistant", content="Your name is Bryan"),
    ]


@pytest.mark.asyncio
async def test_history_limit_returns_most_recent_messages(tmp_path: Path) -> None:
    async with open_checkpointer(tmp_path / "checkpoints.db") as checkpointer:
        orchestrator = _orchestrator(checkpointer, ["Hi"])
        reply = await orchestrator.chat(ChatRequest(message="Hello"))
        history = await orchestrator.get_history(
            GetHistoryRequest(session_id=reply.session_id, limit=1)
        )

    assert history is not None
    assert history.messages == [SessionMessage(role="assistant", content="Hi")]


@pytest.mark.asyncio
async def test_unknown_session_has_no_history(tmp_path: Path) -> None:
    async with open_checkpointer(tmp_path / "checkpoints.db") as checkpointer:
        history = await _orchestrator(checkpointer, []).get_history(
            GetHistoryRequest(session_id="missing")
        )

    assert history is None
