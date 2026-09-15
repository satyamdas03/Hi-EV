# Task 4: Notes vault ingestion

**Files:**
- Create: `src/ev/ingestion/base.py`
- Create: `src/ev/ingestion/notes.py`
- Test: `tests/test_ingestion_notes.py`

**Interfaces:**
- Consumes: `ev.config.Settings.notes_path`; `ev.security.boundary.Blocklist`.
- Produces:
  - `ev.ingestion.base.IngestionSource` abstract class.
  - `ev.ingestion.notes.NotesIngestion` class.
  - `NotesIngestion.ingest()` → `list[dict]` of normalized ingest records.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingestion_notes.py
import tempfile
from pathlib import Path
from ev.config import Settings
from ev.ingestion.notes import NotesIngestion

def test_notes_ingestion_finds_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "robocad.md").write_text("# RoboCAD\nPhase 29 delivered.")
        (root / "ideas.md").write_text("- patent idea for gripper")
        ingester = NotesIngestion(Settings(notes_path=root, personal_only=True))
        records = ingester.ingest()
        assert len(records) == 2
        assert any("Phase 29" in r["content"] for r in records)
        assert all(r["source"] == "notes" for r in records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion_notes.py -v`
Expected: FAIL — `ev.ingestion` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ev/ingestion/__init__.py
from .notes import NotesIngestion

__all__ = ["NotesIngestion"]

# src/ev/ingestion/base.py
from abc import ABC, abstractmethod
from typing import Any

class IngestionSource(ABC):
    @abstractmethod
    def ingest(self) -> list[dict[str, Any]]:
        raise NotImplementedError

# src/ev/ingestion/notes.py
import hashlib
from pathlib import Path
from ev.config import Settings
from ev.security.boundary import Blocklist, personal_only_guard, PersonalOnlyError
from .base import IngestionSource

def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

class NotesIngestion(IngestionSource):
    def __init__(self, config: Settings):
        personal_only_guard(config)
        self.root = config.notes_path
        self.blocklist = Blocklist(work_handles=["financialsimplicity"], work_domains=["financialsimplicity.com"])

    def ingest(self) -> list[dict]:
        records = []
        if not self.root.exists():
            return records
        for path in self.root.rglob("*.md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            rel = str(path.relative_to(self.root))
            if self.blocklist.is_blocked_repo(rel) or self.blocklist.is_blocked_account(rel):
                continue
            records.append({
                "source": "notes",
                "source_id": str(path),
                "content_hash": _hash(content),
                "content": content,
                "project_tag": self._guess_project_tag(content, rel),
                "privacy_level": "personal",
            })
        return records

    def _guess_project_tag(self, content: str, rel_path: str) -> str | None:
        lower = (content + " " + rel_path).lower()
        for keyword in ["robocad", "learningrobotics", "neuralquant", "hi-ev"]:
            if keyword in lower:
                return keyword
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingestion_notes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ev/ingestion/ tests/test_ingestion_notes.py
git commit -m "feat: add notes vault ingestion with blocklist filtering" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

## Important Notes

- `NotesIngestion` must guard against `personal_only=False` and raise `PersonalOnlyError`.
- The blocklist is hardcoded in this task to the work handle/domain from Task 3. Later tasks will move this to config.
- Project tag guessing is keyword-based. Later tasks may use an LLM or embedding-based classifier.

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
