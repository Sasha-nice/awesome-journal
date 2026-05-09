"""/start handler — minimal greeting."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет, я awesome-journal.\n"
        "Скоро здесь появится журнал событий, "
        "пока что я просто отвечаю на /start."
    )
