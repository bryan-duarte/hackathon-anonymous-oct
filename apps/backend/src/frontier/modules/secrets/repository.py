from datetime import UTC, datetime

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS secrets (
    ref TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    ciphertext BLOB NOT NULL,
    created_at TEXT NOT NULL
);
"""


class SecretsRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def init_schema(self) -> None:
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def insert(self, ref: str, label: str, ciphertext: bytes) -> None:
        await self._conn.execute(
            "INSERT INTO secrets (ref, label, ciphertext, created_at) VALUES (?, ?, ?, ?)",
            (ref, label, ciphertext, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    async def get(self, ref: str) -> tuple[str, bytes] | None:
        async with self._conn.execute(
            "SELECT label, ciphertext FROM secrets WHERE ref = ?", (ref,)
        ) as cursor:
            row = await cursor.fetchone()
        return (row["label"], row["ciphertext"]) if row else None
