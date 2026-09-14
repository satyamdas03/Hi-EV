"""Hi-EV settings loader."""

from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Annotated

from pydantic import Field, PlainValidator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _posix_path(value):
    """Preserve POSIX path strings on all platforms."""
    if isinstance(value, str):
        return PurePosixPath(value)
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://localhost:5432/hiev"
    redis_url: str = "redis://localhost:6379/0"
    personal_only: bool = Field(default=True)
    notes_path: Annotated[Path, PlainValidator(_posix_path)] = Field(
        default=Path.home() / "notes"
    )
    github_token: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
