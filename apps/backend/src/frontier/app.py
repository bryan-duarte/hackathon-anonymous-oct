from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from frontier.api.routes import router
from frontier.container import build_clients
from frontier.contracts.jobs import FailUnfinishedRequest
from frontier.core.config import Settings
from frontier.core.db import open_connection

ERROR_KEYS_ECHOING_INPUT = frozenset({"input", "ctx"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()
    conn = await open_connection(settings.database_path)
    try:
        clients = await build_clients(settings, conn)
        await clients.jobs.fail_unfinished(FailUnfinishedRequest(reason="interrupted by restart"))
        app.state.settings = settings
        app.state.clients = clients
        yield
        await clients.migrations.shutdown()
    finally:
        await conn.close()


async def reject_invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    errors_without_input = [
        {key: detail for key, detail in field_error.items() if key not in ERROR_KEYS_ECHOING_INPUT}
        for field_error in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors_without_input}
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Frontier · La Caja Negra", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, reject_invalid_request)
    app.include_router(router)
    return app


app = create_app()
