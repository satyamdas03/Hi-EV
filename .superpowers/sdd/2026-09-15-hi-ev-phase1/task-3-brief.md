# Task 3: Security boundary — personal-only and blocklist

**Files:**
- Create: `src/ev/security/boundary.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `ev.config.Settings.personal_only`.
- Produces:
  - `ev.security.boundary.assert_personal_only(config)` → raises `PersonalOnlyError` if false.
  - `ev.security.boundary.Blocklist` class with `is_blocked_repo(url_or_name)` and `is_blocked_account(handle)`.
  - `ev.security.boundary.personal_only_guard(config)` context manager.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_security.py
import pytest
from ev.config import Settings
from ev.security.boundary import Blocklist, PersonalOnlyError, assert_personal_only, personal_only_guard

def test_assert_personal_only_raises_when_false():
    config = Settings(personal_only=False)
    with pytest.raises(PersonalOnlyError):
        assert_personal_only(config)

def test_blocklist_flags_work_repos():
    bl = Blocklist(work_handles=["financialsimplicity"], work_domains=["financialsimplicity.com"])
    assert bl.is_blocked_repo("https://github.com/financialsimplicity/secret-repo")
    assert bl.is_blocked_repo("https://github.com/acme-corp/secret-repo") is False
    assert bl.is_blocked_account("someone@financialsimplicity.com")

def test_personal_only_guard_accepts_true():
    config = Settings(personal_only=True)
    with personal_only_guard(config):
        pass  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL — `ev.security` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ev/security/__init__.py
from .boundary import Blocklist, PersonalOnlyError, assert_personal_only, personal_only_guard

__all__ = ["Blocklist", "PersonalOnlyError", "assert_personal_only", "personal_only_guard"]

# src/ev/security/boundary.py
from contextlib import contextmanager
from urllib.parse import urlparse
from ev.config import Settings

class PersonalOnlyError(Exception):
    pass

def assert_personal_only(config: Settings) -> None:
    if not config.personal_only:
        raise PersonalOnlyError("EV is configured in personal-only mode; personal_only must be True")

@contextmanager
def personal_only_guard(config: Settings):
    assert_personal_only(config)
    yield

class Blocklist:
    def __init__(self, work_handles=None, work_domains=None):
        self.work_handles = set(work_handles or [])
        self.work_domains = set(work_domains or [])

    def is_blocked_repo(self, url_or_name: str) -> bool:
        lower = url_or_name.lower()
        for handle in self.work_handles:
            if handle.lower() in lower:
                return True
        return False

    def is_blocked_account(self, handle_or_email: str) -> bool:
        lower = handle_or_email.lower()
        for domain in self.work_domains:
            if domain.lower() in lower:
                return True
        for handle in self.work_handles:
            if handle.lower() in lower:
                return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ev/security/ tests/test_security.py
git commit -m "feat: add personal-only security boundary and blocklist" -m "Co-Authored-By: Claude Code <noreply@anthropic.com)"
```

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
