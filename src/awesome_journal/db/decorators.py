"""Decorators for controllers."""
from __future__ import annotations

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
