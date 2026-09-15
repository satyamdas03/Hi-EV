"""Ad-hoc migration for local SQLite DBs created before Phase 3.

Phase 3 added `status`, `snooze_until`, and `last_reminded` columns to the
`deadlines` table. New tables (`people`, `obligations`, `decisions`) are
auto-created by `Base.metadata.create_all`. This script only adds the missing
columns to an existing `deadlines` table when they do not already exist.

Run from the repo root:
    python scripts/migrate_phase3.py
"""

from ev.config import get_settings


def migrate():
    settings = get_settings()
    db_url = settings.database_url

    if not db_url.startswith("sqlite"):
        print(f"Skipping migration for non-SQLite database: {db_url}")
        return

    path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    import sqlite3

    conn = sqlite3.connect(path)
    cur = conn.execute("PRAGMA table_info(deadlines)")
    columns = {row[1] for row in cur.fetchall()}

    added = []
    if "status" not in columns:
        conn.execute("ALTER TABLE deadlines ADD COLUMN status VARCHAR(32) DEFAULT 'open'")
        added.append("status")
    if "snooze_until" not in columns:
        conn.execute("ALTER TABLE deadlines ADD COLUMN snooze_until DATETIME")
        added.append("snooze_until")
    if "last_reminded" not in columns:
        conn.execute("ALTER TABLE deadlines ADD COLUMN last_reminded DATETIME")
        added.append("last_reminded")

    conn.commit()
    conn.close()
    if added:
        print(f"Migration complete: added columns {added} to {path}")
    else:
        print(f"No migration needed; all columns present in {path}")


if __name__ == "__main__":
    migrate()
