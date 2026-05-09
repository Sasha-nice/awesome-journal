"""Bot entry point."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from awesome_journal.bot.config import BotConfig
from awesome_journal.bot.handlers import start as start_handlers


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def run() -> None:
    setup_logging()
    log = logging.getLogger("bot")

    config = BotConfig.from_env()
    if config.emergency_stop:
        log.warning("EMERGENCY_STOP is true — bot is configured to be silent.")
        return

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(start_handlers.router)

    log.info("Starting bot in long-polling mode...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("Bot stopped.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
