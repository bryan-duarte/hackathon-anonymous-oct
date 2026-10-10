from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from frontier.api.deps import get_clients, require_platform_key
from frontier.container import Clients
from frontier.contracts.migrations import (
    GetMigrationStatusRequest,
    MigrationAccepted,
    MigrationRejected,
    MigrationRequest,
    MigrationStatus,
)

router = APIRouter()
migrations_router = APIRouter(prefix="/migrations", dependencies=[Depends(require_platform_key)])

ClientsDep = Annotated[Clients, Depends(get_clients)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@migrations_router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": MigrationRejected}},
)
async def submit_migration(request: MigrationRequest, clients: ClientsDep) -> MigrationAccepted:
    result = await clients.migrations.submit(request)
    if isinstance(result, MigrationRejected):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=result.model_dump()
        )
    return result


@migrations_router.get("/{job_id}")
async def get_migration(job_id: str, clients: ClientsDep) -> MigrationStatus:
    migration = await clients.migrations.get_status(GetMigrationStatusRequest(job_id=job_id))
    if migration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="migration not found")
    return migration


router.include_router(migrations_router)
