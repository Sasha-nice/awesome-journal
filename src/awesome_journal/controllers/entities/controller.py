"""EntitiesController — обёртка над Storage для работы с entities/categories."""
from __future__ import annotations

from typing import TYPE_CHECKING

from awesome_journal.db.decorators import inject_conn
from awesome_journal.models.entity import Entity, TaskCategory
from awesome_journal.models.result import Result

if TYPE_CHECKING:
    import asyncpg

    from awesome_journal.db.storage import Storage


class EntitiesController:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @inject_conn
    async def list_entities_by_type(
        self,
        user_id: int,
        entity_type: str,
        *,
        conn: asyncpg.Connection,
    ) -> Result[list[Entity]]:
        try:
            entities = await self._storage.list_entities_by_type(
                user_id, entity_type, conn=conn
            )
            return Result.success(entities)
        except Exception as e:
            return Result.failure(
                f"list_entities_by_type: {type(e).__name__}: {e}"
            )

    @inject_conn
    async def find_or_create_entity(
        self,
        user_id: int,
        entity_type: str,
        name: str,
        *,
        conn: asyncpg.Connection,
    ) -> Result[Entity]:
        try:
            entity = await self._storage.find_or_create_entity(
                user_id, entity_type, name, conn=conn
            )
            return Result.success(entity)
        except Exception as e:
            return Result.failure(
                f"find_or_create_entity: {type(e).__name__}: {e}"
            )

    @inject_conn
    async def list_task_categories(
        self,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[list[TaskCategory]]:
        try:
            cats = await self._storage.list_task_categories(user_id, conn=conn)
            return Result.success(cats)
        except Exception as e:
            return Result.failure(
                f"list_task_categories: {type(e).__name__}: {e}"
            )

    @inject_conn
    async def find_or_create_task_category(
        self,
        user_id: int,
        name: str,
        *,
        conn: asyncpg.Connection,
    ) -> Result[TaskCategory]:
        try:
            cat = await self._storage.find_or_create_task_category(
                user_id, name, conn=conn
            )
            return Result.success(cat)
        except Exception as e:
            return Result.failure(
                f"find_or_create_task_category: {type(e).__name__}: {e}"
            )
