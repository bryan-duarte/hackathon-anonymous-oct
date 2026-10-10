from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from frontier.api.deps import get_clients, require_platform_key
from frontier.container import Clients
from frontier.contracts.migrations import (
    GetMigrationStatusRequest,
    MigrationAccepted,
    MigrationRejected,
    MigrationRequest,
    MigrationStatus,
)
from frontier.contracts.prompts import Greeting
from frontier.modules.guardrails import GuardrailUnavailableError
from frontier.modules.orchestrator import MissingStructuredResponseError

SAFETY_CHECK_UNAVAILABLE = "Safety check is temporarily unavailable. Please try again in a moment."

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
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": MigrationRejected},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Safety check unavailable"},
    },
)
async def submit_migration(
    request: MigrationRequest, clients: ClientsDep
) -> MigrationAccepted | JSONResponse:
    try:
        submission = await clients.migrations.submit(request)
    except GuardrailUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SAFETY_CHECK_UNAVAILABLE
        ) from error
    if isinstance(submission, MigrationRejected):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=submission.model_dump()
        )
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


router.include_router(migrations_router)
router.include_router(agent_router)
