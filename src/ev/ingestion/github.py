"""GitHub personal repo ingestion source."""

import hashlib
from typing import Any

import httpx

from ev.config import Settings
from ev.security.boundary import Blocklist, PersonalOnlyError, assert_personal_only

from .base import IngestionSource


class GitHubIngestion(IngestionSource):
    BASE = "https://api.github.com"

    def __init__(self, config: Settings):
        assert_personal_only(config)
        self.token = config.github_token.get_secret_value() if config.github_token else None
        self.blocklist = Blocklist(
            work_handles=["financialsimplicity"],
            work_domains=["financialsimplicity.com"],
        )
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
        records = []
        for i in resp.json():
            title = i.get("title", "")
            body = i.get("body", "") or ""
            state = i.get("state", "unknown")
            content = f"{title}\nstate: {state}\n\n{body}"
            records.append(self._record("github_issues", str(i["number"]), content, repo))
        return records

    async def _fetch_prs(self, client: httpx.AsyncClient, repo: str) -> list[dict]:
        url = f"{self.BASE}/repos/{repo}/pulls"
        resp = await client.get(url, params={"per_page": 10, "state": "all"})
        if resp.status_code != 200:
            return []
        records = []
        for p in resp.json():
            title = p.get("title", "")
            body = p.get("body", "") or ""
            state = p.get("state", "unknown")
            content = f"{title}\nstate: {state}\n\n{body}"
            records.append(self._record("github_prs", str(p["number"]), content, repo))
        return records

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
