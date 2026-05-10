"""Bot entry point — composition root.

Orchestrates two frontends (Telegram polling + HTTP /health) sharing a
single AsyncExitStack so resources and runners unwind LIFO on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import AsyncExitStack

from aiohttp import web

from awesome_journal import resources
from awesome_journal.bot.http import build_http_app
from awesome_journal.bot.telegram import build_telegram
from awesome_journal.clients import GeminiClient, LLMClient
from awesome_journal.controllers.allowlist import AllowlistController
from awesome_journal.controllers.entities.controller import EntitiesController
from awesome_journal.controllers.parser.controller import ParserController
from awesome_journal.db.storage import Storage
from awesome_journal.settings import AppSettings

log = logging.getLogger("bot")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


async def run_http(
    stack: AsyncExitStack,
    settings: AppSettings,
    *,
    storage: Storage,
) -> None:
    """Start the HTTP frontend. Returns once the server is listening;
    cleanup is registered on `stack`."""
    app = build_http_app(storage=storage)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, settings.health_host, settings.health_port).start()
    stack.push_async_callback(runner.cleanup)
    log.info(
        "Health server listening on http://%s:%d/health",
        settings.health_host,
        settings.health_port,
    )


async def run_telegram(
    stack: AsyncExitStack,
    settings: AppSettings,
    *,
    allowlist: AllowlistController,
) -> None:
    """Start the Telegram frontend. Blocks until polling stops; bot
    session close is registered on `stack`."""
    bot, dp = build_telegram(token=settings.bot_token, allowlist=allowlist)
    stack.push_async_callback(bot.session.close)

    log.info("Starting bot in long-polling mode...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def run() -> None:
    setup_logging()

    settings = AppSettings()
    if settings.emergency_stop:
        log.warning("EMERGENCY_STOP is true — bot will not start.")
        return

    async with AsyncExitStack() as stack:
        pool = await stack.enter_async_context(resources.db_pool(settings.db_dsn))
        storage = Storage(pool)
        allowlist = AllowlistController(storage)
        entities_controller = EntitiesController(storage)  # noqa: F841 — для Task 10/11

        llm: LLMClient = GeminiClient(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
        )
        parser_controller = ParserController(llm)  # noqa: F841 — будет передан в Task 11

        await run_http(stack, settings, storage=storage)
        try:
            await run_telegram(stack, settings, allowlist=allowlist)
        finally:
            log.info("Shutting down...")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
