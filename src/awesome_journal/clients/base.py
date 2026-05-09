"""LLM client abstractions.

Controllers depend on the `LLMClient` Protocol, not on concrete
implementations. This is the seam for future fallback chaining
(e.g., FallbackLLMClient that tries multiple keys/providers).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pydantic import BaseModel

    from awesome_journal.models.result import Result


@runtime_checkable
class LLMClient(Protocol):
    """Async LLM client returning structured output.

    Implementations MUST never raise: any error becomes `Result.failure(...)`.

    Implementations MAY log usage / latency information internally.
    """

    async def generate_structured[T: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        *,
        temperature: float = 0.0,
        system_instruction: str | None = None,
    ) -> Result[T]: ...
