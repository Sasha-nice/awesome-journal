"""Telegram frontend: builds Bot + Dispatcher with handlers + middlewares wired in.

The composition root calls `build_telegram` and passes only the
resources Telegram-side handlers/middlewares actually need.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pydantic import SecretStr

from awesome_journal.bot.handlers import start as start_handlers
from awesome_journal.bot.middlewares.allowlist import AllowlistMiddleware
from awesome_journal.controllers.allowlist import AllowlistController


def build_telegram(
    *,
    token: SecretStr,
    allowlist: AllowlistController,
) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(AllowlistMiddleware(allowlist))
    dp.include_router(start_handlers.router)
    return bot, dp
