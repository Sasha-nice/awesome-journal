"""Application settings, loaded once from environment / .env file.

This is the single source of truth. Other modules (core, bot, mcp_server)
do NOT read os.environ directly — they receive concrete values from a
Settings instance.
"""
from __future__ import annotations

from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Top-level settings. Reads .env automatically."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr = Field(validation_alias="BOT_TOKEN")
    emergency_stop: bool = Field(default=False, validation_alias="EMERGENCY_STOP")
    default_tz: str = Field(default="UTC", validation_alias="DEFAULT_TZ")

    db_user: str = Field(validation_alias="DB_USER")
    db_password: SecretStr = Field(validation_alias="DB_PASSWORD")
    db_name: str = Field(validation_alias="DB_NAME")
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")

    health_host: str = Field(default="127.0.0.1", validation_alias="HEALTH_HOST")
    health_port: int = Field(default=8080, validation_alias="HEALTH_PORT")

    @property
    def db_dsn(self) -> str:
        """asyncpg-compatible Postgres URL."""
        pwd = quote(self.db_password.get_secret_value(), safe="")
        return (
            f"postgresql://{self.db_user}:{pwd}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
