from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram.enums import ChatType
from aiogram.types import Chat, Message, Update, User

from awesome_journal.bot.middlewares.allowlist import AllowlistMiddleware
from awesome_journal.models.result import Result

_FAKE_USER_ID = 12345


def _msg(*, chat_type: ChatType = ChatType.PRIVATE, user_id: int = _FAKE_USER_ID) -> Message:
    return Message(
        message_id=1,
        date=0,  # type: ignore[arg-type]  # pydantic coerces int → datetime
        chat=Chat(id=user_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="x"),
        text="/start",
    )


def _allowlist(*, ok: bool = True, value: bool = True) -> MagicMock:
    allowlist = MagicMock(name="AllowlistController")
    allowlist.is_allowed = AsyncMock(
        return_value=Result.success(value) if ok else Result.failure("boom"),
    )
    return allowlist


async def test_allows_message_from_allowed_user_in_private_chat() -> None:
    mw = AllowlistMiddleware(_allowlist(ok=True, value=True))
    handler = AsyncMock(return_value="HANDLED")
    update = Update(update_id=1, message=_msg())

    result = await mw(handler, update, {})

    assert result == "HANDLED"
    handler.assert_called_once_with(update, {})


async def test_drops_message_from_user_not_in_allowlist() -> None:
    mw = AllowlistMiddleware(_allowlist(ok=True, value=False))
    handler = AsyncMock()
    update = Update(update_id=1, message=_msg())

    result = await mw(handler, update, {})

    assert result is None
    handler.assert_not_called()


async def test_drops_group_chat_even_for_allowed_user() -> None:
    mw = AllowlistMiddleware(_allowlist(ok=True, value=True))
    handler = AsyncMock()
    update = Update(update_id=1, message=_msg(chat_type=ChatType.GROUP))

    result = await mw(handler, update, {})

    assert result is None
    handler.assert_not_called()


async def test_drops_supergroup_chat_even_for_allowed_user() -> None:
    mw = AllowlistMiddleware(_allowlist(ok=True, value=True))
    handler = AsyncMock()
    update = Update(update_id=1, message=_msg(chat_type=ChatType.SUPERGROUP))

    result = await mw(handler, update, {})

    assert result is None
    handler.assert_not_called()


async def test_drops_when_db_check_fails() -> None:
    mw = AllowlistMiddleware(_allowlist(ok=False))
    handler = AsyncMock()
    update = Update(update_id=1, message=_msg())

    result = await mw(handler, update, {})

    assert result is None
    handler.assert_not_called()


async def test_drops_non_message_update() -> None:
    """Updates без message (callback_query, edited_message и т.п.) — silent drop."""
    mw = AllowlistMiddleware(_allowlist(ok=True, value=True))
    handler = AsyncMock()
    update = Update(update_id=1)

    result = await mw(handler, update, {})

    assert result is None
    handler.assert_not_called()
