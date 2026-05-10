"""EventsController — транзакционная запись типизированного события."""
from __future__ import annotations

from typing import TYPE_CHECKING

from awesome_journal.db.decorators import inject_tx
from awesome_journal.models.parser import (
    FactEvent,
    IdeaEvent,
    MeasurementEvent,
    NoteEvent,
    TaskEvent,
)
from awesome_journal.models.result import Result

if TYPE_CHECKING:
    import asyncpg

    from awesome_journal.controllers.entities.controller import EntitiesController
    from awesome_journal.db.storage import Storage
    from awesome_journal.models.parser import ParsedEvent


class EventsController:
    """Записывает ParsedEvent в БД транзакционно.

    DECISION: EventsController держит EntitiesController через DI,
              а не зовёт Storage entity-методы напрямую.
    Why: Соблюдение слоёв — резолвинг entity это ответственность
         EntitiesController, EventsController координирует.
    Trade-off: граф зависимостей между controllers (events → entities).
               Принимаем, инвариант "контроллеры — DAG без циклов".
    """

    def __init__(self, storage: Storage, entities: EntitiesController) -> None:
        self._storage = storage
        self._entities = entities

    @inject_tx
    async def write_event(
        self,
        parsed: ParsedEvent,
        raw_text: str,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        """Записать одно событие. Атомарно: events + per-type child table.

        DECISION: try/except не нужен — @inject_tx ловит exceptions
                  и возвращает Result.failure("tx error: ...").
        Why: Двойная обёртка (контроллер ловит → Result.failure(A);
             @inject_tx ловит → Result.failure(B)) приводит к потере
             информации о реальной причине. Один уровень — один источник.
        Trade-off: error message формируется @inject_tx, контроллер не
                   контролирует точное содержимое. Принимаем.
        """
        event_id = await self._storage.create_event(
            user_id=user_id,
            event_type=parsed.type,
            occurred_at=parsed.occurred_at,
            raw_text=raw_text,
            conn=conn,
        )

        match parsed:
            case FactEvent():
                return await self._write_fact(parsed, event_id, user_id, conn=conn)
            case MeasurementEvent():
                return await self._write_measurement(
                    parsed, event_id, user_id, conn=conn
                )
            case TaskEvent():
                return await self._write_task(parsed, event_id, user_id, conn=conn)
            case NoteEvent():
                return await self._write_note(parsed, event_id, conn=conn)
            case IdeaEvent():
                return await self._write_idea(parsed, event_id, conn=conn)

    async def _write_fact(
        self,
        parsed: FactEvent,
        event_id: int,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        entity_result = await self._entities.find_or_create_entity(
            user_id, "fact", parsed.name, conn=conn
        )
        if not entity_result.ok:
            return Result.failure(f"fact entity: {entity_result.error}")
        assert entity_result.value is not None  # ok=True гарантирует value

        await self._storage.create_fact_event(
            event_id=event_id,
            entity_id=entity_result.value.id,
            conn=conn,
        )
        return Result.success(None)

    async def _write_measurement(
        self,
        parsed: MeasurementEvent,
        event_id: int,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        entity_result = await self._entities.find_or_create_entity(
            user_id, "measurement", parsed.name, conn=conn
        )
        if not entity_result.ok:
            return Result.failure(f"measurement entity: {entity_result.error}")
        assert entity_result.value is not None

        await self._storage.create_measurement_event(
            event_id=event_id,
            entity_id=entity_result.value.id,
            value=parsed.value,
            unit=parsed.unit,
            conn=conn,
        )
        return Result.success(None)

    async def _write_task(
        self,
        parsed: TaskEvent,
        event_id: int,
        user_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        category_id: int | None = None
        if parsed.category:  # пустая строка = категория не определена
            cat_result = await self._entities.find_or_create_task_category(
                user_id, parsed.category, conn=conn
            )
            if not cat_result.ok:
                return Result.failure(f"task category: {cat_result.error}")
            assert cat_result.value is not None
            category_id = cat_result.value.id

        await self._storage.create_task_event(
            event_id=event_id,
            title=parsed.title,
            category_id=category_id,
            due_date=parsed.due_at,
            conn=conn,
        )
        return Result.success(None)

    async def _write_note(
        self,
        parsed: NoteEvent,
        event_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        await self._storage.create_note_event(
            event_id=event_id,
            text=parsed.text,
            conn=conn,
        )
        return Result.success(None)

    async def _write_idea(
        self,
        parsed: IdeaEvent,
        event_id: int,
        *,
        conn: asyncpg.Connection,
    ) -> Result[None]:
        await self._storage.create_idea_event(
            event_id=event_id,
            text=parsed.text,
            conn=conn,
        )
        return Result.success(None)
