"""Tests for EventsController."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from awesome_journal.controllers.events.controller import EventsController
from awesome_journal.models.entity import Entity, TaskCategory
from awesome_journal.models.parser import (
    FactEvent,
    IdeaEvent,
    MeasurementEvent,
    NoteEvent,
    TaskEvent,
)
from awesome_journal.models.result import Result


class _FakeAcquire:
    async def __aenter__(self) -> Any:
        conn = MagicMock(name="conn")
        tx = MagicMock(name="tx")
        tx.start = AsyncMock()
        tx.commit = AsyncMock()
        tx.rollback = AsyncMock()
        conn.transaction = MagicMock(return_value=tx)
        return conn

    async def __aexit__(self, *_: object) -> None:
        return None


def _make_storage(**method_mocks: AsyncMock) -> MagicMock:
    storage = MagicMock(name="Storage")
    storage.acquire = MagicMock(return_value=_FakeAcquire())
    storage.create_event = AsyncMock(return_value=42)  # default event_id
    storage.create_fact_event = AsyncMock(return_value=None)
    storage.create_measurement_event = AsyncMock(return_value=None)
    storage.create_task_event = AsyncMock(return_value=None)
    storage.create_note_event = AsyncMock(return_value=None)
    storage.create_idea_event = AsyncMock(return_value=None)
    for name, mock in method_mocks.items():
        setattr(storage, name, mock)
    return storage


def _make_entities(
    *,
    entity: Entity | None = None,
    entity_failure: str | None = None,
    category: TaskCategory | None = None,
    category_failure: str | None = None,
) -> MagicMock:
    entities = MagicMock(name="EntitiesController")

    if entity_failure is not None:
        entities.find_or_create_entity = AsyncMock(
            return_value=Result.failure(entity_failure)
        )
    else:
        ent = entity or Entity(
            id=1,
            user_id=1,
            type="fact",
            name="default",
            aliases=[],
            created_at=datetime(2026, 5, 9, tzinfo=UTC),
        )
        entities.find_or_create_entity = AsyncMock(return_value=Result.success(ent))

    if category_failure is not None:
        entities.find_or_create_task_category = AsyncMock(
            return_value=Result.failure(category_failure)
        )
    else:
        cat = category or TaskCategory(
            id=10, user_id=1, name="default", aliases=[], is_system=False,
        )
        entities.find_or_create_task_category = AsyncMock(
            return_value=Result.success(cat)
        )
    return entities


# ----- 5 happy path tests -----


async def test_write_fact() -> None:
    entity = Entity(
        id=7, user_id=1, type="fact", name="зарядка",
        aliases=[], created_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    storage = _make_storage()
    entities = _make_entities(entity=entity)
    ctrl = EventsController(storage, entities)

    parsed = FactEvent(
        type="fact", name="зарядка",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "сделал зарядку", user_id=1)

    assert result.ok
    storage.create_event.assert_awaited_once()
    entities.find_or_create_entity.assert_awaited_once()
    storage.create_fact_event.assert_awaited_once()
    call_kwargs = storage.create_fact_event.call_args.kwargs
    assert call_kwargs["event_id"] == 42
    assert call_kwargs["entity_id"] == 7


async def test_write_measurement() -> None:
    entity = Entity(
        id=5, user_id=1, type="measurement", name="шаги",
        aliases=[], created_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    storage = _make_storage()
    entities = _make_entities(entity=entity)
    ctrl = EventsController(storage, entities)

    parsed = MeasurementEvent(
        type="measurement", name="шаги", value=8000.0, unit="шагов",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "8к шагов", user_id=1)

    assert result.ok
    storage.create_measurement_event.assert_awaited_once()
    call_kwargs = storage.create_measurement_event.call_args.kwargs
    assert call_kwargs["entity_id"] == 5
    assert call_kwargs["value"] == 8000.0
    assert call_kwargs["unit"] == "шагов"


async def test_write_task_with_category() -> None:
    cat = TaskCategory(id=3, user_id=1, name="работа", aliases=[], is_system=False)
    storage = _make_storage()
    entities = _make_entities(category=cat)
    ctrl = EventsController(storage, entities)

    parsed = TaskEvent(
        type="task", title="разобраться с api", category="работа",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
        due_at=date(2026, 5, 15),
    )
    result = await ctrl.write_event(parsed, "...", user_id=1)

    assert result.ok
    entities.find_or_create_task_category.assert_awaited_once()
    storage.create_task_event.assert_awaited_once()
    call_kwargs = storage.create_task_event.call_args.kwargs
    assert call_kwargs["category_id"] == 3
    assert call_kwargs["title"] == "разобраться с api"
    assert call_kwargs["due_date"] == date(2026, 5, 15)


async def test_write_note() -> None:
    storage = _make_storage()
    entities = _make_entities()
    ctrl = EventsController(storage, entities)

    parsed = NoteEvent(
        type="note", text="встреча прошла отлично",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "встреча прошла отлично", user_id=1)

    assert result.ok
    storage.create_note_event.assert_awaited_once()
    entities.find_or_create_entity.assert_not_awaited()
    entities.find_or_create_task_category.assert_not_awaited()


async def test_write_idea() -> None:
    storage = _make_storage()
    entities = _make_entities()
    ctrl = EventsController(storage, entities)

    parsed = IdeaEvent(
        type="idea", text="изучить rust",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "хочу изучить rust", user_id=1)

    assert result.ok
    storage.create_idea_event.assert_awaited_once()
    entities.find_or_create_entity.assert_not_awaited()


# ----- 3 edge case tests -----


async def test_fact_entity_failure_propagates() -> None:
    """Если EntitiesController вернул failure при резолвинге name —
    write_event возвращает failure, и create_fact_event НЕ вызывается."""
    storage = _make_storage()
    entities = _make_entities(entity_failure="db unavailable")
    ctrl = EventsController(storage, entities)

    parsed = FactEvent(
        type="fact", name="зарядка",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "...", user_id=1)

    assert not result.ok
    assert "fact entity" in (result.error or "")
    assert "db unavailable" in (result.error or "")
    storage.create_fact_event.assert_not_awaited()


async def test_task_category_failure_propagates() -> None:
    """Failure при резолвинге category → write_event возвращает failure."""
    storage = _make_storage()
    entities = _make_entities(category_failure="conn lost")
    ctrl = EventsController(storage, entities)

    parsed = TaskEvent(
        type="task", title="купить хлеб", category="дом",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "...", user_id=1)

    assert not result.ok
    assert "task category" in (result.error or "")
    storage.create_task_event.assert_not_awaited()


async def test_task_without_category_skips_category_lookup() -> None:
    """parsed.category="" → find_or_create_task_category НЕ вызывается,
    create_task_event получает category_id=None."""
    storage = _make_storage()
    entities = _make_entities()
    ctrl = EventsController(storage, entities)

    parsed = TaskEvent(
        type="task", title="купить хлеб", category="",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    result = await ctrl.write_event(parsed, "...", user_id=1)

    assert result.ok
    entities.find_or_create_task_category.assert_not_awaited()
    storage.create_task_event.assert_awaited_once()
    assert storage.create_task_event.call_args.kwargs["category_id"] is None
