"""Middleware that silently drops messages from non-allowed users
and from non-private chats."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Message, TelegramObject, Update

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from awesome_journal.controllers.allowlist import AllowlistController


class AllowlistMiddleware(BaseMiddleware):
    """Outer middleware on `dp.update`: silently drops everything that
    isn't a message from an allowed user in a private chat.

    Events at this level are `Update` objects; we extract the inner
    message and decide. Non-message updates (callback_query, etc.) are
    silently dropped as well — we don't handle them yet.
    """

    def __init__(self, allowlist: AllowlistController) -> None:
        self._allowlist = allowlist

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message: Message | None = (
            event.message if isinstance(event, Update) else None
        )
        if message is None:
            return None

        if message.chat.type != ChatType.PRIVATE:
            return None

        if message.from_user is None:
            return None

        result = await self._allowlist.is_allowed(message.from_user.id)
        if not result.ok or result.value is not True:
            return None

        return await handler(event, data)
