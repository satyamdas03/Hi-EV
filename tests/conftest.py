"""Shared pytest configuration for Hi-EV."""

import os
from pathlib import Path

# Force tests to use an isolated async SQLite database so the suite can run
# without a local Postgres server. Production code still defaults to Postgres
# via ev.config.Settings.database_url.
_TEST_DB_PATH = (Path(__file__).resolve().parent / "hiev_test.db").as_posix()
os.environ["EV_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"
