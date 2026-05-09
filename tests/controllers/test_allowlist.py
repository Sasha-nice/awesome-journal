from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from awesome_journal.controllers.allowlist import AllowlistController


class _FakeAcquire:
    def __init__(self, *, raises: BaseException | None = None) -> None:
        self._raises = raises

    async def __aenter__(self):
        if self._raises is not None:
            raise self._raises
        return MagicMock(name="conn")

    async def __aexit__(self, *_: object) -> None:
        return None


def _make_storage(
    *,
    user_is_allowed: AsyncMock | None = None,
    acquire_raises: BaseException | None = None,
) -> MagicMock:
    storage = MagicMock(name="Storage")
    storage.acquire = MagicMock(
        return_value=_FakeAcquire(raises=acquire_raises)
    )
    storage.user_is_allowed = user_is_allowed or AsyncMock(return_value=False)
    return storage


async def test_returns_true_when_user_in_allowlist() -> None:
    storage = _make_storage(user_is_allowed=AsyncMock(return_value=True))
    ctrl = AllowlistController(storage)

    result = await ctrl.is_allowed(123)

    assert result.ok
    assert result.value is True


async def test_returns_false_when_user_not_in_allowlist() -> None:
    storage = _make_storage(user_is_allowed=AsyncMock(return_value=False))
    ctrl = AllowlistController(storage)

    result = await ctrl.is_allowed(123)

    assert result.ok
    assert result.value is False


async def test_returns_failure_when_storage_raises() -> None:
    storage = _make_storage(
        user_is_allowed=AsyncMock(side_effect=RuntimeError("boom"))
    )
    ctrl = AllowlistController(storage)

    result = await ctrl.is_allowed(123)

    assert not result.ok
    assert result.error is not None
    assert "boom" in result.error


async def test_returns_failure_when_acquire_raises() -> None:
    """inject_conn должен поймать ошибку acquire() и вернуть Result.failure."""
    storage = _make_storage(acquire_raises=OSError("connection refused"))
    ctrl = AllowlistController(storage)

    result = await ctrl.is_allowed(123)

    assert not result.ok
    assert result.error is not None
    assert "connection refused" in result.error
