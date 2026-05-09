"""Health-check controller — business logic layer.

Responsibility: convert a "is the system healthy?" question into a
concrete answer, hiding all infrastructure details (connection
acquisition, SQL exceptions) behind a Result[HealthStatus] return type.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from awesome_journal.db.decorators import inject_conn
from awesome_journal.models.health import HealthStatus
from awesome_journal.models.result import Result

if TYPE_CHECKING:
    import asyncpg

    from awesome_journal.db.storage import Storage

log = logging.getLogger(__name__)


class HealthController:
    """Always returns Result, never raises."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @inject_conn
    async def check(self, *, conn: asyncpg.Connection) -> Result[HealthStatus]:
        try:
            alive = await self._storage.ping(conn)
            return Result.success(HealthStatus(db_alive=alive))
        except Exception as e:
            log.warning("Health check SQL failed: %s", e)
            return Result.failure(str(e))
