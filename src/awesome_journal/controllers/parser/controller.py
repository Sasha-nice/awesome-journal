"""ParserController — превращает свободный текст в типизированное событие."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from awesome_journal.clients.base import LLMClient
from awesome_journal.controllers.parser.prompt import (
    SYSTEM_INSTRUCTION,
    format_user_prompt,
)
from awesome_journal.models.parser import (
    ParserContext,
    ParseResult,
    RawParseResponse,
    to_typed,
)
from awesome_journal.models.result import Result

MAX_INPUT_LENGTH = 2000
PAST_WINDOW_DAYS = 30
FUTURE_WINDOW_DAYS = 365


class ParserController:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def parse(
        self,
        text: str,
        context: ParserContext,
        now: datetime | None = None,
    ) -> Result[ParseResult]:
        if err := self._validate_input(text):
            return Result.failure(err)

        effective_now = now if now is not None else datetime.now(UTC)

        llm_result = await self._llm.generate_structured(
            format_user_prompt(text, context, effective_now.isoformat()),
            RawParseResponse,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        if not llm_result.ok:
            return Result.failure(f"llm error: {llm_result.error}")
        assert llm_result.value is not None  # для mypy после проверки .ok

        return self._interpret_response(llm_result.value, effective_now)

    @staticmethod
    def _validate_input(text: str) -> str | None:
        """Pre-LLM проверки. Возвращает текст ошибки или None если ok."""
        if not text.strip():
            return "empty input"
        if len(text) > MAX_INPUT_LENGTH:
            return f"input exceeds {MAX_INPUT_LENGTH} chars"
        return None

    def _interpret_response(
        self,
        response: RawParseResponse,
        now: datetime,
    ) -> Result[ParseResult]:
        """Постобработка ответа LLM: multiple_events, заполнение occurred_at,
        проверка окна, конверсия Raw→Typed."""
        # DECISION: Multiple events in one message → fail entire parse,
        #           not "pick the most important one".
        # Why: MVP simplification. Telling the user "split into separate
        #      messages" produces cleaner data than letting LLM choose
        #      which event to drop. Raw text is preserved in DB for
        #      future reanalysis.
        # Trade-off: Worse UX on first multi-event messages. Revisit
        #            after collecting real usage patterns.
        if response.multiple_events_detected:
            return Result.failure("multiple_events")

        if response.event is None:
            return Result.success(ParseResult(event=None))

        raw_event = response.event
        if raw_event.occurred_at is None:
            raw_event = raw_event.model_copy(update={"occurred_at": now})

        if raw_event.occurred_at is None or not self._is_in_window(
            raw_event.occurred_at, now
        ):
            return Result.success(ParseResult(event=None))

        typed = to_typed(raw_event)
        if typed is None:
            # битый контракт типа → отбрасываем как и out-of-range
            return Result.success(ParseResult(event=None))

        return Result.success(ParseResult(event=typed))

    @staticmethod
    def _is_in_window(occurred_at: datetime, now: datetime) -> bool:
        lower = now - timedelta(days=PAST_WINDOW_DAYS)
        upper = now + timedelta(days=FUTURE_WINDOW_DAYS)
        return lower <= occurred_at <= upper
