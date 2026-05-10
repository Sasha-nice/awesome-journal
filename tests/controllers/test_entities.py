"""Tests for EntitiesController."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from awesome_journal.controllers.entities.controller import EntitiesController
from awesome_journal.models.entity import Entity, TaskCategory


class _FakeAcquire:
    async def __aenter__(self) -> Any:
        return MagicMock(name="conn")

    async def __aexit__(self, *_: object) -> None:
        return None


def _make_storage(**method_mocks: AsyncMock) -> MagicMock:
    """Build a Storage stub: acquire() yields a mock conn; method mocks
    overlay any of `list_entities_by_type`, `find_or_create_entity`, etc."""
    storage = MagicMock(name="Storage")
    storage.acquire = MagicMock(return_value=_FakeAcquire())
    for name, mock in method_mocks.items():
        setattr(storage, name, mock)
    return storage


def _entity(name: str = "running", entity_id: int = 1) -> Entity:
    return Entity(
        id=entity_id,
        user_id=1,
        type="measurement",
        name=name,
        aliases=[],
        created_at=datetime(2026, 5, 9, tzinfo=UTC),
    )


def _task_category(name: str = "работа", category_id: int = 1) -> TaskCategory:
    return TaskCategory(
        id=category_id,
        user_id=1,
        name=name,
        aliases=[],
        is_system=False,
    )


async def test_list_entities_by_type_success() -> None:
    storage = _make_storage(
        list_entities_by_type=AsyncMock(return_value=[_entity("running"), _entity("walking", 2)]),
    )
    ctrl = EntitiesController(storage)

    result = await ctrl.list_entities_by_type(1, "measurement")

    assert result.ok
    assert result.value is not None
    assert [e.name for e in result.value] == ["running", "walking"]


async def test_find_or_create_entity_success() -> None:
    storage = _make_storage(
        find_or_create_entity=AsyncMock(return_value=_entity("running", 7)),
    )
    ctrl = EntitiesController(storage)

    result = await ctrl.find_or_create_entity(1, "measurement", "running")

    assert result.ok
    assert result.value is not None
    assert result.value.id == 7
    assert result.value.name == "running"


async def test_list_task_categories_success() -> None:
    storage = _make_storage(
        list_task_categories=AsyncMock(
            return_value=[_task_category("дом", 1), _task_category("работа", 2)]
        ),
    )
    ctrl = EntitiesController(storage)

    result = await ctrl.list_task_categories(1)

    assert result.ok
    assert result.value is not None
    assert [c.name for c in result.value] == ["дом", "работа"]


async def test_find_or_create_task_category_success() -> None:
    storage = _make_storage(
        find_or_create_task_category=AsyncMock(return_value=_task_category("работа", 5)),
    )
    ctrl = EntitiesController(storage)

    result = await ctrl.find_or_create_task_category(1, "работа")

    assert result.ok
    assert result.value is not None
    assert result.value.id == 5
    assert result.value.name == "работа"


async def test_storage_exception_propagates_as_failure() -> None:
    """Storage кидает → контроллер ловит и возвращает Result.failure."""
    storage = _make_storage(
        find_or_create_entity=AsyncMock(side_effect=RuntimeError("db is on fire")),
    )
    ctrl = EntitiesController(storage)

    result = await ctrl.find_or_create_entity(1, "measurement", "running")

    assert not result.ok
    assert "RuntimeError" in (result.error or "")
    assert "db is on fire" in (result.error or "")
