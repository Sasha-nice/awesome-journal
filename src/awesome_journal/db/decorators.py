"""Decorators for controllers."""
from __future__ import annotations

import contextvars
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from awesome_journal.models.result import Result

log = logging.getLogger(__name__)


def inject_conn[T](
    method: Callable[..., Awaitable[Result[T]]],
) -> Callable[..., Awaitable[Result[T]]]:
    """Acquire a connection from `self._storage` and pass it as `conn` kwarg.

    The decorated method must:
    - be a coroutine method on a class with `self._storage: Storage`
    - accept `conn: asyncpg.Connection` as a keyword argument
    - return `Result[T]`

    If `conn` is already in kwargs, the existing connection is used (this
    supports nested calls inside an outer transaction in the future).

    Connection-acquisition errors are caught here and converted to
    `Result.failure(...)`, so callers never see an exception from the
    controller — keeping the rule "controllers never propagate" honest.

    Usage:

        class FooController:
            def __init__(self, storage: Storage) -> None:
                self._storage = storage

            @inject_conn
            async def do_thing(self, x: int, *, conn) -> Result[X]:
                ...
    """

    @wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Result[T]:
        if "conn" in kwargs:
            return await method(self, *args, **kwargs)
        try:
            async with self._storage.acquire() as conn:
                return await method(self, *args, conn=conn, **kwargs)
        except Exception as e:
            log.warning("inject_conn: failed to acquire connection: %s", e)
            return Result.failure(str(e))

    return wrapper


# Контекст-переменная для детектирования вложенности @inject_tx.
# Сбрасывается в default (False) при выходе из обёртки.
_in_tx: contextvars.ContextVar[bool] = contextvars.ContextVar("_in_tx", default=False)


def inject_tx[T](
    method: Callable[..., Awaitable[Result[T]]],
) -> Callable[..., Awaitable[Result[T]]]:
    """Открывает транзакцию для метода контроллера.

    Контракт:
    - Метод должен принимать `conn: asyncpg.Connection` как kwarg
    - Возвращает `Result[T]` — на success коммитит, на failure откатывает
    - На exception — откатывает + возвращает `Result.failure("tx error: ...")`
    - Запрещена вложенность: если уже в `@inject_tx` — raise `RuntimeError`

    DECISION: Result.failure тоже триггерит rollback (а не commit).
    Why: failure означает что контроллер счёл результат невалидным;
         частичные записи в БД хуже чем чистый откат.
    Trade-off: невозможно сохранить частичный результат при failure;
               принимаем — у нас единичные события, частичность бессмысленна.
    """

    @wraps(method)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Result[T]:
        if _in_tx.get():
            raise RuntimeError(
                "@inject_tx вложен в другой @inject_tx — запрещено"
            )

        async with self._storage.acquire() as conn:
            token = _in_tx.set(True)
            try:
                tx = conn.transaction()
                await tx.start()
                try:
                    result = await method(self, *args, conn=conn, **kwargs)
                except Exception as e:
                    await tx.rollback()
                    return Result.failure(f"tx error: {type(e).__name__}: {e}")

                if result.ok:
                    await tx.commit()
                else:
                    await tx.rollback()
                return result
            finally:
                _in_tx.reset(token)

    return wrapper
