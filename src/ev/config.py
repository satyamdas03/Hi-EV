"""Hi-EV settings loader."""

from functools import lru_cache
from pathlib import Path, PurePosixPath

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    notes_path: PurePosixPath | Path = Field(default=PurePosixPath(Path.home() / "notes"))
    github_token: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_provider: str = "nvidia"
    llm_model: str = "meta/llama-3.3-70b-instruct"
    google_enabled: bool = False
    google_credentials_path: Path | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
