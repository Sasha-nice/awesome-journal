"""Storage — single data access object for the whole app.

Wraps the connection pool and exposes:
- `acquire()` — used by `@inject_conn` to get a per-call connection.
- Business-level SQL methods (`ping`, future `get_user`, `list_events`, ...)
  that take the connection explicitly and run queries.

Controllers receive a Storage instance and compose its methods inside
their try/except + Result wrappers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


class Storage:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def acquire(self) -> asyncpg.pool.PoolAcquireContext:
        """Acquire a connection. Used by `@inject_conn`."""
        return self._pool.acquire()

    async def ping(self, conn: asyncpg.Connection) -> bool:
        """True iff the DB answers `SELECT 1` with 1."""
        return await conn.fetchval("SELECT 1") == 1
