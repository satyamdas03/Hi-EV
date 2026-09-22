"""Hi-EV settings loader."""

from functools import lru_cache
from pathlib import Path, PurePosixPath

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _default_database_url() -> str:
    """Default to a local SQLite file so EV runs without a system Postgres install."""
    return f"sqlite+aiosqlite:///{Path.home() / '.hiev' / 'hiev.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default_factory=_default_database_url)
    redis_url: str = "redis://localhost:6379/0"
    personal_only: bool = Field(default=True)
    notes_path: PurePosixPath | Path = Field(default=PurePosixPath(Path.home() / "notes"))
    github_token: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_provider: str = "nvidia"
    llm_model: str = "meta/llama-3.2-11b-vision-instruct"
    google_enabled: bool = False
    google_credentials_path: Path | None = None
    robocad_path: Path | None = None
    learningrobotics_path: Path | None = None
    hiev_path: Path | None = None

    # Personal-only boundary: comma-separated handles/domains to never ingest or act on.
    blocked_handles: str | list[str] = Field(default_factory=list)
    blocked_domains: str | list[str] = Field(default_factory=list)

    # Local embedding model for semantic memory.
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    # GitHub repos to monitor for personal ingestion (comma-separated owner/name pairs).
    github_repos: str | list[str] = Field(default_factory=list)

    # Alert loop / quiet hours
    alert_interval_sec: int = 900
    alert_window_hours: int = 72
    quiet_start: str = "22:00"
    quiet_end: str = "08:00"
    kill_switch: bool = False

    # Background ingestion loop interval in seconds (default 5 minutes).
    ingest_interval_sec: int = 300

    # Phase B — Reasoning Router + Eval Harness feature flags.
    enable_reasoning_router: bool = Field(default=False)
    llm_stream_enabled: bool = Field(default=True)

    # Phase C — Proactive alerts, morning brief, and optional Telegram relay.
    proactive_alerts_enabled: bool = Field(default=True)
    morning_brief_enabled: bool = Field(default=True)
    morning_brief_time: str = Field(default="08:00")
    telegram_enabled: bool = Field(default=False)
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    # Guard model / prompt-injection classifier settings.
    guard_llm_enabled: bool = Field(default=True)
    guard_caution_threshold: float = Field(default=0.6)
    guard_block_patterns: str | list[str] = Field(default_factory=list)
    guard_untrusted_downgrade_tier: int = Field(default=1)

    @field_validator("blocked_handles", "blocked_domains", "github_repos", "guard_block_patterns", mode="before")
    @classmethod
    def _parse_csv(cls, value):
        if isinstance(value, str):
            return _split_csv(value)
        return value or []


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
