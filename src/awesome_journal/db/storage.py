"""Storage — single data access object for the whole app.

Wraps the connection pool and exposes:
- `acquire()` — used by `@inject_conn` to get a per-call connection.
- Business-level SQL methods that take the connection as the last,
  keyword-only argument and run queries.

Controllers receive a Storage instance and compose its methods inside
their try/except + Result wrappers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from awesome_journal.models.entity import Entity, TaskCategory

if TYPE_CHECKING:
    from datetime import date, datetime

    import asyncpg


class Storage:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def acquire(self) -> asyncpg.pool.PoolAcquireContext:
        return self._pool.acquire()

    async def ping(self, *, conn: asyncpg.Connection) -> bool:
        return await conn.fetchval("SELECT 1") == 1

    async def user_is_allowed(
        self,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> bool:
        return bool(
            await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM allowed_users WHERE user_id = $1)",
                user_id,
            )
        )

    # ----- entities -----

    async def list_entities_by_type(
        self,
        user_id: int,
        entity_type: str,
        *,
        conn: asyncpg.Connection,
    ) -> list[Entity]:
        """Список всех entities юзера данного типа. ORDER BY name ASC."""
        rows = await conn.fetch(
            """
            SELECT id, user_id, type, name, aliases, created_at
            FROM entities
            WHERE user_id = $1 AND type = $2
            ORDER BY name ASC
            """,
            user_id,
            entity_type,
        )
        return [Entity.model_validate(dict(r)) for r in rows]

    async def find_or_create_entity(
        self,
        user_id: int,
        entity_type: str,
        name: str,
        *,
        conn: asyncpg.Connection,
    ) -> Entity:
        """Идемпотентно: находит existing entity или создаёт новую.

        Использует `ON CONFLICT (user_id, type, name) DO UPDATE SET name=EXCLUDED.name`
        (no-op обновление) — нужно чтобы RETURNING сработал и в случае conflict.
        DO NOTHING бы не вернул row.

        aliases при создании = пустой массив. Изменение алиасов не входит
        в Task 9 — будет отдельным методом в Task 12+.
        """
        row = await conn.fetchrow(
            """
            INSERT INTO entities (user_id, type, name, aliases)
            VALUES ($1, $2, $3, '{}')
            ON CONFLICT (user_id, type, name) DO UPDATE
                SET name = EXCLUDED.name
            RETURNING id, user_id, type, name, aliases, created_at
            """,
            user_id,
            entity_type,
            name,
        )
        assert row is not None  # RETURNING всегда возвращает при ON CONFLICT DO UPDATE
        return Entity.model_validate(dict(row))

    # ----- task categories -----

    async def list_task_categories(
        self,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> list[TaskCategory]:
        """Список категорий задач юзера. ORDER BY name ASC."""
        rows = await conn.fetch(
            """
            SELECT id, user_id, name, aliases, is_system
            FROM task_categories
            WHERE user_id = $1
            ORDER BY name ASC
            """,
            user_id,
        )
        return [TaskCategory.model_validate(dict(r)) for r in rows]

    async def find_or_create_task_category(
        self,
        user_id: int,
        name: str,
        *,
        conn: asyncpg.Connection,
    ) -> TaskCategory:
        """Идемпотентно для категорий задач.

        aliases=[], is_system=false при создании.
        """
        row = await conn.fetchrow(
            """
            INSERT INTO task_categories (user_id, name, aliases, is_system)
            VALUES ($1, $2, '{}', false)
            ON CONFLICT (user_id, name) DO UPDATE
                SET name = EXCLUDED.name
            RETURNING id, user_id, name, aliases, is_system
            """,
            user_id,
            name,
        )
        assert row is not None
        return TaskCategory.model_validate(dict(row))

    # ----- events (parent + per-type children) -----

    async def create_event(
        self,
        user_id: int,
        event_type: str,
        occurred_at: datetime,
        raw_text: str,
        *,
        conn: asyncpg.Connection,
    ) -> int:
        """Создаёт запись в events, возвращает event_id для child INSERT."""
        event_id = await conn.fetchval(
            """
            INSERT INTO events (user_id, type, occurred_at, raw_text)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user_id,
            event_type,
            occurred_at,
            raw_text,
        )
        assert event_id is not None  # RETURNING всегда возвращает после INSERT
        return event_id

    async def create_fact_event(
        self,
        event_id: int,
        entity_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO fact_events (event_id, entity_id)
            VALUES ($1, $2)
            """,
            event_id,
            entity_id,
        )

    async def create_measurement_event(
        self,
        event_id: int,
        entity_id: int,
        value: float,
        unit: str,
        *,
        conn: asyncpg.Connection,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO measurement_events (event_id, entity_id, value, unit)
            VALUES ($1, $2, $3, $4)
            """,
            event_id,
            entity_id,
            value,
            unit,
        )

    async def create_task_event(
        self,
        event_id: int,
        title: str,
        category_id: int | None,
        due_date: date | None,
        *,
        conn: asyncpg.Connection,
    ) -> None:
        """category_id опционально (после миграции 0003 NULLABLE).

        priority и done_at не передаются — используются дефолты схемы
        (priority=0, done_at=NULL).
        """
        await conn.execute(
            """
            INSERT INTO task_events (event_id, title, category_id, due_date)
            VALUES ($1, $2, $3, $4)
            """,
            event_id,
            title,
            category_id,
            due_date,
        )

    async def create_note_event(
        self,
        event_id: int,
        text: str,
        *,
        conn: asyncpg.Connection,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO note_events (event_id, text)
            VALUES ($1, $2)
            """,
            event_id,
            text,
        )

    async def create_idea_event(
        self,
        event_id: int,
        text: str,
        *,
        conn: asyncpg.Connection,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO idea_events (event_id, text)
            VALUES ($1, $2)
            """,
            event_id,
            text,
        )
