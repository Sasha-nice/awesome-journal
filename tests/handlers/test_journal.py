"""Tests for journal handler."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from awesome_journal.bot.handlers.journal import handle_text
from awesome_journal.models.parser import FactEvent, ParseResult
from awesome_journal.models.result import Result

_FAKE_USER_ID = 12345


def _make_message(text: str = "сделал зарядку", user_id: int = _FAKE_USER_ID) -> MagicMock:
    """Mock Message с text, from_user.id, answer()."""
    msg = MagicMock(name="Message")
    msg.text = text
    msg.from_user = MagicMock(id=user_id)
    msg.answer = AsyncMock()
    return msg


def _make_parser(parse_result: Result[ParseResult]) -> MagicMock:
    parser = MagicMock(name="ParserController")
    parser.parse = AsyncMock(return_value=parse_result)
    return parser


def _make_events(write_result: Result[None]) -> MagicMock:
    events = MagicMock(name="EventsController")
    events.write_event = AsyncMock(return_value=write_result)
    return events


def _make_entities(
    *,
    fact_failure: str | None = None,
    measurement_failure: str | None = None,
    category_failure: str | None = None,
) -> MagicMock:
    entities = MagicMock(name="EntitiesController")

    def _result(failure: str | None) -> Result[list[Any]]:
        return Result.failure(failure) if failure is not None else Result.success([])

    async def list_entities(user_id: int, entity_type: str) -> Result[list[Any]]:
        if entity_type == "fact":
            return _result(fact_failure)
        return _result(measurement_failure)

    entities.list_entities_by_type = AsyncMock(side_effect=list_entities)
    entities.list_task_categories = AsyncMock(return_value=_result(category_failure))
    return entities


def _success_parse_with_fact() -> Result[ParseResult]:
    fact = FactEvent(
        type="fact",
        name="зарядка",
        occurred_at=datetime(2026, 5, 9, tzinfo=UTC),
    )
    return Result.success(ParseResult(event=fact))


# === Tests ===


async def test_happy_path_records_event_and_responds_ok() -> None:
    msg = _make_message("сделал зарядку")
    parser = _make_parser(_success_parse_with_fact())
    events = _make_events(Result.success(None))
    entities = _make_entities()

    await handle_text(msg, parser=parser, events=events, entities=entities)

    parser.parse.assert_awaited_once()
    events.write_event.assert_awaited_once()
    msg.answer.assert_awaited_once_with("✓")


async def test_long_message_skips_parser_and_responds_fail() -> None:
    msg = _make_message("a" * 2001)
    parser = _make_parser(_success_parse_with_fact())  # не должен вызываться
    events = _make_events(Result.success(None))
    entities = _make_entities()

    await handle_text(msg, parser=parser, events=events, entities=entities)

    parser.parse.assert_not_awaited()
    events.write_event.assert_not_awaited()
    msg.answer.assert_awaited_once_with("✗")


async def test_context_load_failure_responds_fail() -> None:
    msg = _make_message()
    parser = _make_parser(_success_parse_with_fact())
    events = _make_events(Result.success(None))
    entities = _make_entities(fact_failure="db unavailable")

    await handle_text(msg, parser=parser, events=events, entities=entities)

    parser.parse.assert_not_awaited()
    msg.answer.assert_awaited_once_with("✗")


async def test_parser_failure_responds_fail() -> None:
    msg = _make_message()
    parser = _make_parser(Result.failure("multiple_events"))
    events = _make_events(Result.success(None))
    entities = _make_entities()

    await handle_text(msg, parser=parser, events=events, entities=entities)

    parser.parse.assert_awaited_once()
    events.write_event.assert_not_awaited()
    msg.answer.assert_awaited_once_with("✗")


async def test_parser_success_with_no_event_responds_fail() -> None:
    """Парсер вернул ParseResult(event=None) — приветствие/мусор."""
    msg = _make_message("привет")
    parser = _make_parser(Result.success(ParseResult(event=None)))
    events = _make_events(Result.success(None))
    entities = _make_entities()

    await handle_text(msg, parser=parser, events=events, entities=entities)

    parser.parse.assert_awaited_once()
    events.write_event.assert_not_awaited()
    msg.answer.assert_awaited_once_with("✗")


async def test_events_write_failure_responds_fail() -> None:
    msg = _make_message()
    parser = _make_parser(_success_parse_with_fact())
    events = _make_events(Result.failure("tx error: ConnectionError"))
    entities = _make_entities()

    await handle_text(msg, parser=parser, events=events, entities=entities)

    events.write_event.assert_awaited_once()
    msg.answer.assert_awaited_once_with("✗")
