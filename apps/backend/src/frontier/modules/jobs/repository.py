from collections.abc import Mapping
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    base_url TEXT NOT NULL,
    context TEXT NOT NULL,
    service_key_ref TEXT NOT NULL,
    team_token_ref TEXT NOT NULL,
    deployed_url TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    at TEXT NOT NULL,
    phase TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_events_job_id ON job_events (job_id, id);
"""

UPDATABLE_COLUMNS = frozenset({"status", "phase", "deployed_url", "error"})


class JobsRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def init_schema(self) -> None:
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def insert_job(self, job: Mapping[str, Any]) -> None:
        columns = ", ".join(job)
        placeholders = ", ".join("?" for _ in job)
        await self._conn.execute(
            f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", tuple(job.values())
        )
        await self._conn.commit()

    async def update_job(self, job_id: str, fields: Mapping[str, Any], updated_at: str) -> None:
        unknown = set(fields) - UPDATABLE_COLUMNS
        if unknown:
            raise ValueError(f"not updatable: {sorted(unknown)}")
        assignments = ", ".join(f"{column} = ?" for column in [*fields, "updated_at"])
        await self._conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?",
            (*fields.values(), updated_at, job_id),
        )
        await self._conn.commit()

    async def insert_event(self, job_id: str, at: str, phase: str, message: str) -> None:
        await self._conn.execute(
            "INSERT INTO job_events (job_id, at, phase, message) VALUES (?, ?, ?, ?)",
            (job_id, at, phase, message),
        )
        await self._conn.commit()

    async def get_job(self, job_id: str) -> aiosqlite.Row | None:
        async with self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            return await cursor.fetchone()

    async def latest_events(self, job_id: str, limit: int) -> list[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM (SELECT * FROM job_events WHERE job_id = ? ORDER BY id DESC LIMIT ?)"
            " ORDER BY id",
            (job_id, limit),
        ) as cursor:
            return list(await cursor.fetchall())

    async def unfinished_job_ids(self) -> list[str]:
        async with self._conn.execute(
            "SELECT id FROM jobs WHERE status IN ('queued', 'running')"
        ) as cursor:
            return [row["id"] for row in await cursor.fetchall()]
