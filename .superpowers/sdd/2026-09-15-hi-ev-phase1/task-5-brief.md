# Task 5: GitHub personal repo ingestion

**Files:**
- Create: `src/ev/ingestion/github.py`
- Test: `tests/test_ingestion_github.py`

**Interfaces:**
- Consumes: `ev.config.Settings.github_token`, `ev.config.Settings.personal_only`.
- Produces:
  - `ev.ingestion.github.GitHubIngestion` class.
  - `GitHubIngestion.ingest()` → `list[dict]` of normalized records for commits, issues, PRs, and workflow runs.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingestion_github.py
import pytest
from unittest.mock import patch, MagicMock
from ev.config import Settings
from ev.ingestion.github import GitHubIngestion

def test_github_ingestion_requires_personal_only():
    with pytest.raises(Exception):
        GitHubIngestion(Settings(personal_only=False, github_token="ghp_test"))

@patch("ev.ingestion.github.httpx.AsyncClient")
async def test_github_ingestion_parses_commits(mock_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"sha": "abc123", "commit": {"message": "feat: add solver", "author": {"date": "2026-09-10T12:00:00Z"}}}
    ]
    mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
    ingester = GitHubIngestion(Settings(personal_only=True, github_token="ghp_test"))
    ingester.add_repo("satyamdas03", "RoboCAD")
    records = await ingester.ingest()
    assert any(r["source"] == "github_commits" and "abc123" in r["source_id"] for r in records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion_github.py -v`
Expected: FAIL — `ev.ingestion.github` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/ev/ingestion/github.py
import hashlib
from typing import Any
import httpx
from ev.config import Settings
from ev.security.boundary import Blocklist, personal_only_guard, PersonalOnlyError
from .base import IngestionSource

class GitHubIngestion(IngestionSource):
    BASE = "https://api.github.com"

    def __init__(self, config: Settings):
        personal_only_guard(config)
        self.token = config.github_token.get_secret_value() if config.github_token else None
        self.blocklist = Blocklist(work_handles=["financialsimplicity"], work_domains=["financialsimplicity.com"])
        self._repos: list[str] = []

    def add_repo(self, owner: str, name: str):
        repo = f"{owner}/{name}"
        if self.blocklist.is_blocked_repo(repo) or self.blocklist.is_blocked_account(owner):
            raise PersonalOnlyError(f"Repo {repo} is blocked by personal-only boundary")
        self._repos.append(repo)

    async def ingest(self) -> list[dict[str, Any]]:
        records = []
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        async with httpx.AsyncClient(headers=headers) as client:
            for repo in self._repos:
                records.extend(await self._fetch_commits(client, repo))
                records.extend(await self._fetch_issues(client, repo))
                records.extend(await self._fetch_prs(client, repo))
        return records

    async def _fetch_commits(self, client: httpx.AsyncClient, repo: str) -> list[dict]:
        url = f"{self.BASE}/repos/{repo}/commits"
        resp = await client.get(url, params={"per_page": 10})
        if resp.status_code != 200:
            return []
        records = []
        for item in resp.json():
            message = item.get("commit", {}).get("message", "")
            records.append(self._record("github_commits", item["sha"], message, repo))
        return records

    async def _fetch_issues(self, client: httpx.AsyncClient, repo: str) -> list[dict]:
        url = f"{self.BASE}/repos/{repo}/issues"
        resp = await client.get(url, params={"per_page": 10, "state": "all"})
        if resp.status_code != 200:
            return []
        return [self._record("github_issues", str(i["number"]), i.get("title", "") + "\n" + i.get("body", ""), repo) for i in resp.json()]

    async def _fetch_prs(self, client: httpx.AsyncClient, repo: str) -> list[dict]:
        url = f"{self.BASE}/repos/{repo}/pulls"
        resp = await client.get(url, params={"per_page": 10, "state": "all"})
        if resp.status_code != 200:
            return []
        return [self._record("github_prs", str(p["number"]), p.get("title", "") + "\n" + p.get("body", ""), repo) for p in resp.json()]

    def _record(self, source: str, source_id: str, content: str, repo: str) -> dict:
        content = content or ""
        return {
            "source": source,
            "source_id": f"{repo}:{source_id}",
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "content": content,
            "project_tag": repo.split("/")[-1].lower(),
            "privacy_level": "personal",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingestion_github.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ev/ingestion/github.py tests/test_ingestion_github.py
git commit -m "feat: add GitHub personal repo ingestion" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

## Global Constraints (verbatim)
- Python 3.12+
- No work data: all connectors must check a `personal_only=True` flag and refuse to initialize if false.
- Secrets in `.env` only: never commit keys; use `python-dotenv`.
- Every task ends with a passing test and a commit.
- Commit messages end with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- Local-first: all sensitive memory lives in local Postgres.
- Idempotent ingestion: every ingested item carries `source_id` and a content hash; re-syncs do not duplicate.
