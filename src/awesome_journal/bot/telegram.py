"""Telegram frontend: builds Bot + Dispatcher with handlers wired in.

The composition root calls `build_telegram` and passes only the
resources Telegram-side handlers actually need. Today that's just the
token — when a handler starts using the DB pool, add `pool` to the
signature and stash it in `dp[...]` for aiogram's per-handler injection.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pydantic import SecretStr

from awesome_journal.bot.handlers import start as start_handlers


def build_telegram(*, token: SecretStr) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(start_handlers.router)
    return bot, dp
