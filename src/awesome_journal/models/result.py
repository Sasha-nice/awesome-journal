"""Generic result type for fallible operations.

Used by db controllers to wrap operations that may raise: instead of
propagating exceptions, the controller catches them and returns a Result
with an error message. Callers must check `result.ok` before accessing
`result.value`.
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result[T](BaseModel):
    """Either a successful value or an error message.

    Pydantic generic — validate-and-serialize friendly.
    """

    value: T | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def success(cls, value: T) -> Result[T]:
        return cls(value=value, error=None)

    @classmethod
    def failure(cls, error: str) -> Result[T]:
        return cls(value=None, error=error)
