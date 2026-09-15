# Task 1: Project scaffold and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/ev/__init__.py`
- Create: `src/ev/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: none.
- Produces: `ev.config.Settings` — Pydantic settings class with `database_url`, `redis_url`, `github_token`, `notes_path`, `personal_only`, `openai_api_key` (optional for Phase 2), `anthropic_api_key` (optional for Phase 2).
- Produces: `ev.config.get_settings()` → `Settings`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from ev.config import get_settings

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("EV_DATABASE_URL", "postgresql://localhost:5432/hiev_test")
    monkeypatch.setenv("EV_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("EV_PERSONAL_ONLY", "true")
    monkeypatch.setenv("EV_NOTES_PATH", "/tmp/notes")
    monkeypatch.setenv("EV_GITHUB_TOKEN", "ghp_test")
    settings = get_settings()
    assert settings.database_url == "postgresql://localhost:5432/hiev_test"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.personal_only is True
    assert str(settings.notes_path) == "/tmp/notes"
    assert settings.github_token.get_secret_value() == "ghp_test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_loads_from_env -v`
Expected: FAIL — `ev.config` or `Settings` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ev/__init__.py
__version__ = "0.1.0"

# src/ev/config.py
from functools import lru_cache
from pathlib import Path
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
    notes_path: Path = Field(default=Path.home() / "notes")
    github_token: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```toml
# pyproject.toml
[project]
name = "hi-ev"
version = "0.1.0"
description = "EV — personal AI operating system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "pgvector>=0.2.5",
    "psycopg2-binary>=2.9.9",
    "asyncpg>=0.29.0",
    "redis>=5.0.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "httpx>=0.27.0",
    "click>=8.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "factory-boy>=3.3.0",
    "ruff>=0.4.0",
]

[project.scripts]
ev = "ev.cli.main:cli"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```text
# .env.example
EV_DATABASE_URL=postgresql://localhost:5432/hiev
EV_REDIS_URL=redis://localhost:6379/0
EV_PERSONAL_ONLY=true
EV_NOTES_PATH=/path/to/your/notes
EV_GITHUB_TOKEN=ghp_xxxxxxxx
EV_ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
EV_OPENAI_API_KEY=sk-xxxxxxxx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_settings_loads_from_env -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example src/ev/__init__.py src/ev/config.py tests/test_config.py
git commit -m "feat: add project config and settings loader" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
