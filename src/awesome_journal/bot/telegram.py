"""Telegram frontend: builds Bot + Dispatcher with handlers + middlewares wired in.

The composition root calls `build_telegram` and passes only the
resources Telegram-side handlers/middlewares actually need. Controllers
listed as `Dispatcher` keyword arguments are auto-injected into handler
kwargs by aiogram (via `dp[key] = value`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from awesome_journal.bot.handlers import journal as journal_handlers
from awesome_journal.bot.handlers import start as start_handlers
from awesome_journal.bot.middlewares.allowlist import AllowlistMiddleware

if TYPE_CHECKING:
    from pydantic import SecretStr

    from awesome_journal.controllers.allowlist import AllowlistController
    from awesome_journal.controllers.entities.controller import EntitiesController
    from awesome_journal.controllers.events.controller import EventsController
    from awesome_journal.controllers.parser.controller import ParserController


def build_telegram(
    *,
    token: SecretStr,
    allowlist: AllowlistController,
    parser: ParserController,
    events: EventsController,
    entities: EntitiesController,
) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(
        parser=parser,
        events=events,
        entities=entities,
    )
    dp.update.outer_middleware(AllowlistMiddleware(allowlist))
    dp.include_router(start_handlers.router)
    dp.include_router(journal_handlers.router)
    return bot, dp
