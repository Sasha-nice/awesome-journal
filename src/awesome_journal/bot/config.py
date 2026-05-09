"""Bot configuration loaded from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class BotConfig:
    bot_token: str
    emergency_stop: bool

    @classmethod
    def from_env(cls) -> BotConfig:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Put it in .env or export it."
            )
        emergency = os.environ.get("EMERGENCY_STOP", "false").lower() == "true"
        return cls(bot_token=token, emergency_stop=emergency)
