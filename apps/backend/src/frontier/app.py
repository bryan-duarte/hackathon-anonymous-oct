from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from frontier.api.routes import router
from frontier.container import build_clients
from frontier.contracts.jobs import FailUnfinishedRequest
from frontier.core.config import Settings
from frontier.core.db import open_connection


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


def create_app() -> FastAPI:
    app = FastAPI(title="Frontier · La Caja Negra", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
