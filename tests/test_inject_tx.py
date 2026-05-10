"""Tests for the @inject_tx decorator."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from awesome_journal.db.decorators import _in_tx, inject_tx
from awesome_journal.models.result import Result


class _FakeAcquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, *_: object) -> None:
        return None


def _make_storage() -> tuple[MagicMock, MagicMock]:
    """Return (storage_mock, tx_mock).

    `storage_mock.acquire()` yields a conn whose `.transaction()` returns
    `tx_mock`. `tx_mock.start/commit/rollback` are AsyncMocks that tests
    can introspect.
    """
    tx = MagicMock(name="tx")
    tx.start = AsyncMock(name="tx.start")
    tx.commit = AsyncMock(name="tx.commit")
    tx.rollback = AsyncMock(name="tx.rollback")

    conn = MagicMock(name="conn")
    conn.transaction = MagicMock(return_value=tx)

    storage = MagicMock(name="Storage")
    storage.acquire = MagicMock(return_value=_FakeAcquire(conn))
    return storage, tx


@pytest.fixture(autouse=True)
def _reset_in_tx() -> Any:
    """Изолируем ContextVar между тестами — он module-level."""
    token = _in_tx.set(False)
    try:
        yield
    finally:
        _in_tx.reset(token)


class _FakeController:
    """Контроллер с двумя @inject_tx-методами для тестов nesting."""

    def __init__(self, storage: MagicMock) -> None:
        self._storage = storage

    @inject_tx
    async def succeed(self, *, conn: Any) -> Result[int]:  # noqa: ARG002
        return Result.success(42)

    @inject_tx
    async def fail(self, *, conn: Any) -> Result[int]:  # noqa: ARG002
        return Result.failure("explicit failure")

    @inject_tx
    async def boom(self, *, conn: Any) -> Result[int]:  # noqa: ARG002
        raise ValueError("kaboom")

    @inject_tx
    async def call_inner(self, *, conn: Any) -> Result[int]:  # noqa: ARG002
        # Внутри — ещё один @inject_tx, должен бросить RuntimeError.
        return await self.succeed()

    @inject_tx
    async def needs_conn(self, *, conn: Any) -> Result[Any]:
        return Result.success(conn)


async def test_commit_on_success() -> None:
    storage, tx = _make_storage()
    ctrl = _FakeController(storage)

    result = await ctrl.succeed()

    assert result.ok
    assert result.value == 42
    tx.start.assert_awaited_once()
    tx.commit.assert_awaited_once()
    tx.rollback.assert_not_awaited()


async def test_rollback_on_failure() -> None:
    storage, tx = _make_storage()
    ctrl = _FakeController(storage)

    result = await ctrl.fail()

    assert not result.ok
    assert result.error == "explicit failure"
    tx.start.assert_awaited_once()
    tx.commit.assert_not_awaited()
    tx.rollback.assert_awaited_once()


async def test_rollback_on_exception() -> None:
    storage, tx = _make_storage()
    ctrl = _FakeController(storage)

    result = await ctrl.boom()

    assert not result.ok
    assert "ValueError" in (result.error or "")
    assert "kaboom" in (result.error or "")
    tx.start.assert_awaited_once()
    tx.commit.assert_not_awaited()
    tx.rollback.assert_awaited_once()


async def test_conn_passed_via_kwarg() -> None:
    storage, _ = _make_storage()
    ctrl = _FakeController(storage)

    result = await ctrl.needs_conn()

    assert result.ok
    # storage.acquire().__aenter__ вернул conn — он же должен прийти в метод
    assert result.value is not None


async def test_nested_tx_raises() -> None:
    """outer @inject_tx → inner @inject_tx внутри.

    Внешний вызов ловит RuntimeError из inner как любое exception
    и возвращает Result.failure("tx error: RuntimeError: ...").
    """
    storage, tx = _make_storage()
    ctrl = _FakeController(storage)

    result = await ctrl.call_inner()

    assert not result.ok
    assert "RuntimeError" in (result.error or "")
    assert "вложен" in (result.error or "")
    # outer открыл tx и откатил его на exception
    tx.rollback.assert_awaited_once()
    tx.commit.assert_not_awaited()
