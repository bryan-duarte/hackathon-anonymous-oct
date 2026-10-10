from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from frontier.api.deps import get_clients, require_platform_key
from frontier.container import Clients
from frontier.contracts.guardrails import GuardrailRejection
from frontier.contracts.migrations import (
    GetMigrationStatusRequest,
    MigrationAccepted,
    MigrationRequest,
    MigrationStatus,
)
from frontier.contracts.orchestrator import ChatReply, ChatRequest
from frontier.contracts.prompts import Greeting
from frontier.contracts.sessions import (
    DEFAULT_HISTORY_LIMIT,
    GetHistoryRequest,
    SessionHistory,
    SessionId,
)
from frontier.modules.orchestrator import MissingStructuredResponseError

GUARDRAIL_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": GuardrailRejection},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Safety check unavailable"},
}

router = APIRouter()
migrations_router = APIRouter(prefix="/migrations", dependencies=[Depends(require_platform_key)])
agent_router = APIRouter(prefix="/agent", dependencies=[Depends(require_platform_key)])

ClientsDep = Annotated[Clients, Depends(get_clients)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@migrations_router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MigrationAccepted,
    responses=GUARDRAIL_RESPONSES,
)
async def submit_migration(
    request: MigrationRequest, clients: ClientsDep
) -> MigrationAccepted | JSONResponse:
    submission = await clients.migrations.submit(request)
    if isinstance(submission, GuardrailRejection):
        return _guardrail_rejection_response(submission)
    return submission


@migrations_router.get("/{job_id}")
async def get_migration(job_id: str, clients: ClientsDep) -> MigrationStatus:
    migration = await clients.migrations.get_status(GetMigrationStatusRequest(job_id=job_id))
    if migration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="migration not found")
    return migration


@agent_router.post("/greeting")
async def greet_agent(clients: ClientsDep) -> Greeting:
    try:
        return await clients.orchestrator.greet()
    except MissingStructuredResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@agent_router.post("/chat", response_model=ChatReply, responses=GUARDRAIL_RESPONSES)
async def chat_with_agent(request: ChatRequest, clients: ClientsDep) -> ChatReply | JSONResponse:
    chat_outcome = await clients.orchestrator.chat(request)
    if isinstance(chat_outcome, GuardrailRejection):
        return _guardrail_rejection_response(chat_outcome)
    return chat_outcome


@agent_router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: SessionId,
    clients: ClientsDep,
    limit: Annotated[int, Query(gt=0)] = DEFAULT_HISTORY_LIMIT,
) -> SessionHistory:
    history = await clients.orchestrator.get_history(
        GetHistoryRequest(session_id=session_id, limit=limit)
    )
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return history


def _guardrail_rejection_response(rejection: GuardrailRejection) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=rejection.model_dump(mode="json")
    )


router.include_router(migrations_router)
router.include_router(agent_router)
