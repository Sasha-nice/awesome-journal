"""Journal handler — текстовое сообщение от allowed user → запись события.

Flow:
    1. Длина >2000 → ✗
    2. asyncio.gather: загрузить fact_names + measurement_names + task_categories
    3. Если любой list_* failure → ✗
    4. parser.parse(text, context) → если failure или event=None → ✗
    5. events.write_event(event, raw_text, user_id) → если failure → ✗
    6. → ✓
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import Message

from awesome_journal.models.parser import (
    ParserContext,
    category_to_hint,
    entity_to_hint,
)

if TYPE_CHECKING:
    from awesome_journal.controllers.entities.controller import EntitiesController
    from awesome_journal.controllers.events.controller import EventsController
    from awesome_journal.controllers.parser.controller import ParserController

log = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000
OK = "✓"
FAIL = "✗"

router = Router(name="journal")


@router.message(F.text)
async def handle_text(
    message: Message,
    parser: ParserController,
    events: EventsController,
    entities: EntitiesController,
) -> None:
    # F.text фильтр гарантирует что text есть; private chats only —
    # AllowlistMiddleware гарантирует что from_user тоже задан.
    assert message.text is not None
    assert message.from_user is not None

    text = message.text
    user_id = message.from_user.id

    # 1. Длина (транспортное ограничение, не парсерное — парсер свою
    #    проверку оставляет defense in depth).
    if len(text) > MAX_MESSAGE_LENGTH:
        await message.answer(FAIL)
        return

    # 2. Загрузить ParserContext параллельно (3 запроса к БД, без транзакции).
    fact_result, measurement_result, category_result = await asyncio.gather(
        entities.list_entities_by_type(user_id, "fact"),
        entities.list_entities_by_type(user_id, "measurement"),
        entities.list_task_categories(user_id),
    )

    # 3. Любой failure → ✗
    if not fact_result.ok or not measurement_result.ok or not category_result.ok:
        log.warning(
            "journal: context load failed: facts=%s measurements=%s cats=%s",
            fact_result.error,
            measurement_result.error,
            category_result.error,
        )
        await message.answer(FAIL)
        return

    assert fact_result.value is not None
    assert measurement_result.value is not None
    assert category_result.value is not None

    context = ParserContext(
        fact_names=[entity_to_hint(e) for e in fact_result.value],
        measurement_names=[entity_to_hint(e) for e in measurement_result.value],
        task_categories=[category_to_hint(c) for c in category_result.value],
    )

    # 4. Парсинг
    parse_result = await parser.parse(text, context)
    if not parse_result.ok:
        log.warning("journal: parse failed: %s", parse_result.error)
        await message.answer(FAIL)
        return

    assert parse_result.value is not None
    if parse_result.value.event is None:
        # success + event=None: парсер ничего не извлёк (приветствие/мусор).
        await message.answer(FAIL)
        return

    # 5. Запись события (под @inject_tx внутри events.write_event).
    write_result = await events.write_event(
        parse_result.value.event,
        raw_text=text,
        user_id=user_id,
    )
    if not write_result.ok:
        log.warning("journal: write_event failed: %s", write_result.error)
        await message.answer(FAIL)
        return

    # 6. Успех
    await message.answer(OK)
