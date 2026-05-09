"""Allowlist controller — checks if a user can use the bot."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from awesome_journal.db.decorators import inject_conn
from awesome_journal.models.result import Result

if TYPE_CHECKING:
    import asyncpg

    from awesome_journal.db.storage import Storage

log = logging.getLogger(__name__)


class AllowlistController:
    """Always returns Result, never raises."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @inject_conn
    async def is_allowed(
        self, user_id: int, *, conn: asyncpg.Connection
    ) -> Result[bool]:
        try:
            allowed = await self._storage.user_is_allowed(conn, user_id)
            return Result.success(allowed)
        except Exception as e:
            log.warning("is_allowed check failed: %s", e)
            return Result.failure(str(e))
