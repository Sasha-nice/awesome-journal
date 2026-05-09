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
        return self._pool.acquire()

    async def ping(self, conn: asyncpg.Connection) -> bool:
        return await conn.fetchval("SELECT 1") == 1

    async def user_is_allowed(self, conn: asyncpg.Connection, user_id: int) -> bool:
        return bool(
            await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM allowed_users WHERE user_id = $1)",
                user_id,
            )
        )
