"""Parser models: context, raw LLM contract, typed discriminated union, conversion."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from awesome_journal.models.entity import Entity, TaskCategory

# ============================================================
# Context (input для парсера)
# ============================================================


class EntityHint(BaseModel):
    """Известная сущность (fact / measurement) с её алиасами."""

    name: str
    aliases: list[str] = Field(default_factory=list)


class CategoryHint(BaseModel):
    """Известная категория задач."""

    name: str
    aliases: list[str] = Field(default_factory=list)


class ParserContext(BaseModel):
    """Контекст для парсинга. Передаётся в каждый вызов parse().

    В Task 8 все списки всегда пустые (БД entities ещё не наполняется).
    Расширение происходит в Task 9-11 без изменения этого API.

    idea_names отсутствует намеренно: у idea нет name (только text),
    нормализовать нечего.
    """

    fact_names: list[EntityHint] = Field(default_factory=list)
    measurement_names: list[EntityHint] = Field(default_factory=list)
    task_categories: list[CategoryHint] = Field(default_factory=list)


# ============================================================
# Typed events (то что видит остальной код)
# ============================================================


class FactEvent(BaseModel):
    type: Literal["fact"]
    name: str
    occurred_at: datetime


class MeasurementEvent(BaseModel):
    type: Literal["measurement"]
    name: str
    value: float
    unit: str
    occurred_at: datetime


class TaskEvent(BaseModel):
    type: Literal["task"]
    title: str
    category: str  # "" если LLM не определил
    occurred_at: datetime  # время упоминания
    due_at: date | None = None  # дата без времени, БД хранит как DATE


class NoteEvent(BaseModel):
    type: Literal["note"]
    text: str
    occurred_at: datetime


class IdeaEvent(BaseModel):
    type: Literal["idea"]
    text: str
    occurred_at: datetime


ParsedEvent = Annotated[
    FactEvent | MeasurementEvent | TaskEvent | NoteEvent | IdeaEvent,
    Field(discriminator="type"),
]


class ParseResult(BaseModel):
    """Результат успешного парсинга. event=None означает что LLM не извлёк
    ничего полезного (приветствие, мусор, всё out-of-range, битый контракт типа).
    """

    event: ParsedEvent | None


# ============================================================
# Raw events (контракт с LLM, плоская модель)
# ============================================================
#
# DECISION: Two model layers — RawParsedEvent (flat) and ParsedEvent
#           (discriminated union).
# Why: Gemini response_schema unreliable on $ref/oneOf generated from
#      Pydantic discriminated unions (schema rejection or discriminator
#      ignored). Flat model with all fields renders predictably.
# Trade-off: Weaker validation at LLM boundary (LLM can return
#            type=measurement with empty value); recovered by to_typed()
#            which enforces type-specific contract before exposing
#            ParsedEvent to the rest of the codebase.


class RawParsedEvent(BaseModel):
    """Плоская модель для Gemini response_schema.

    Все поля всех типов в одном объекте. LLM заполняет только
    релевантные для type, остальные оставляет пустыми.
    """

    type: Literal["fact", "measurement", "task", "note", "idea"]
    occurred_at: datetime | None = None  # None → controller заполняет = now

    # fact / measurement
    name: str = ""

    # measurement
    value: float | None = None
    unit: str = ""

    # task
    title: str = ""
    category: str = ""
    due_at: date | None = None

    # note / idea
    text: str = ""


class RawParseResponse(BaseModel):
    """Top-level контракт с LLM. Gemini требует объект на верхнем уровне."""

    multiple_events_detected: bool
    event: RawParsedEvent | None


# ============================================================
# Конверсия Raw → Typed
# ============================================================
#
# DECISION: to_typed returns None on broken type contract (instead of
#           raising or returning Result).
# Why: Symmetric with how the controller handles out-of-range
#      occurred_at — silent drop, not failure. Treats LLM type-contract
#      violations as "noisy output to filter" rather than "system error".
# Trade-off: We lose the signal that LLM produced malformed output.
#            Acceptable in MVP — if rates of None returns become high,
#            add metrics later (tech debt).


def to_typed(raw: RawParsedEvent) -> ParsedEvent | None:
    """Конвертирует RawParsedEvent в типизированный ParsedEvent.

    Возвращает None если LLM нарушил контракт типа (не заполнил
    обязательные для type поля). Битые события молча отбрасываются.

    К моменту вызова to_typed у raw.occurred_at уже не должно быть None
    (контроллер заполняет = now до вызова). Если всё-таки None —
    отбрасываем.
    """
    if raw.occurred_at is None:
        return None

    match raw.type:
        case "fact":
            if not raw.name:
                return None
            return FactEvent(
                type="fact",
                name=raw.name,
                occurred_at=raw.occurred_at,
            )
        case "measurement":
            if not raw.name or raw.value is None or not raw.unit:
                return None
            return MeasurementEvent(
                type="measurement",
                name=raw.name,
                value=raw.value,
                unit=raw.unit,
                occurred_at=raw.occurred_at,
            )
        case "task":
            if not raw.title:
                return None
            return TaskEvent(
                type="task",
                title=raw.title,
                category=raw.category,
                occurred_at=raw.occurred_at,
                due_at=raw.due_at,
            )
        case "note":
            if not raw.text:
                return None
            return NoteEvent(
                type="note",
                text=raw.text,
                occurred_at=raw.occurred_at,
            )
        case "idea":
            if not raw.text:
                return None
            return IdeaEvent(
                type="idea",
                text=raw.text,
                occurred_at=raw.occurred_at,
            )


# ============================================================
# DB → Hint конверсии (для построения ParserContext в хендлере)
# ============================================================


def entity_to_hint(e: Entity) -> EntityHint:
    """Конвертирует DB-сущность в подсказку для парсера.

    Парсер не нуждается в id/user_id/created_at — только name + aliases
    для нормализации.
    """
    return EntityHint(name=e.name, aliases=e.aliases)


def category_to_hint(c: TaskCategory) -> CategoryHint:
    """Конвертирует DB-категорию задачи в подсказку для парсера."""
    return CategoryHint(name=c.name, aliases=c.aliases)
