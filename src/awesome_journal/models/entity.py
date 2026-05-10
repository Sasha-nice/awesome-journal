"""DB models for entities and task categories."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Entity(BaseModel):
    """Сущность в БД: fact / measurement / idea / note / task name.

    DB-модель. Отличается от EntityHint в models/parser.py — у Hint нет
    id и user_id, потому что Hint это input для парсера (LLM не нужен id).
    """

    id: int
    user_id: int
    type: Literal["fact", "measurement", "task", "note", "idea"]
    name: str
    aliases: list[str]
    created_at: datetime


class TaskCategory(BaseModel):
    """Категория задачи в БД."""

    id: int
    user_id: int
    name: str
    aliases: list[str]
    is_system: bool
