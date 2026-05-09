"""Application-level resource providers.

Long-lived resources (DB pool, etc.) live here as async context managers.
The composition root in bot/main.py uses them; lower layers (controllers,
handlers) receive built resources as constructor arguments.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

log = logging.getLogger(__name__)


@asynccontextmanager
async def db_pool(
    dsn: str,
    *,
    min_size: int = 1,
    max_size: int = 5,
    command_timeout: float = 10.0,
) -> AsyncIterator[asyncpg.Pool]:
    """Create and dispose of an asyncpg connection pool."""
    log.info("Creating DB connection pool (max_size=%d)", max_size)
    pool = await asyncpg.create_pool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
    )
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    try:
        yield pool
    finally:
        log.info("Closing DB connection pool")
        await pool.close()
