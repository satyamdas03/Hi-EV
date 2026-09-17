"""Tests for the GitHub personal repo ingestion source."""

from unittest.mock import MagicMock, patch

import pytest

from ev.config import Settings
from ev.ingestion.github import GitHubIngestion
from ev.security.boundary import PersonalOnlyError


def test_github_ingestion_requires_personal_only():
    with pytest.raises(PersonalOnlyError):
        GitHubIngestion(Settings(personal_only=False, github_token="ghp_test"))


@patch("ev.ingestion.github.httpx.AsyncClient")
async def test_github_ingestion_parses_commits(mock_client):
    commit_response = MagicMock()
    commit_response.status_code = 200
    commit_response.json.return_value = [
        {
            "sha": "abc123",
            "commit": {
                "message": "feat: add solver",
                "author": {"date": "2026-09-10T12:00:00Z"},
            },
        }
    ]
    empty_response = MagicMock()
    empty_response.status_code = 200
    empty_response.json.return_value = []

    def mock_get(url, **kwargs):
        if url.endswith("/commits"):
            return commit_response
        return empty_response

    mock_client.return_value.__aenter__.return_value.get.side_effect = mock_get

    ingester = GitHubIngestion(Settings(personal_only=True, github_token="ghp_test"))
    ingester.add_repo("satyamdas03", "RoboCAD")
    records = await ingester.ingest()

    assert any(
        r["source"] == "github_commits" and "abc123" in r["source_id"] for r in records
    )
    assert all(r["source_id"] for r in records)
    assert all(r["content_hash"] for r in records)
    assert all(r["privacy_level"] == "personal" for r in records)


def test_github_ingestion_blocks_work_repos():
    ingester = GitHubIngestion(
        Settings(
            personal_only=True,
            github_token="ghp_test",
            blocked_handles=["financialsimplicity"],
            blocked_domains=["financialsimplicity.com"],
        )
    )
    with pytest.raises(PersonalOnlyError):
        ingester.add_repo("financialsimplicity", "secret-repo")


@patch("ev.ingestion.github.httpx.AsyncClient")
async def test_github_ingestion_parses_issues_and_prs(mock_client):
    issue_response = MagicMock()
    issue_response.status_code = 200
    issue_response.json.return_value = [
        {"number": 7, "title": "bug: solver crash", "body": "steps to reproduce"}
    ]
    pr_response = MagicMock()
    pr_response.status_code = 200
    pr_response.json.return_value = [
        {"number": 8, "title": "feat: add solver", "body": "PR description"}
    ]
    empty_response = MagicMock()
    empty_response.status_code = 200
    empty_response.json.return_value = []

    def mock_get(url, **kwargs):
        if url.endswith("/issues"):
            return issue_response
        if url.endswith("/pulls"):
            return pr_response
        return empty_response

    mock_client.return_value.__aenter__.return_value.get.side_effect = mock_get

    ingester = GitHubIngestion(Settings(personal_only=True, github_token="ghp_test"))
    ingester.add_repo("satyamdas03", "RoboCAD")
    records = await ingester.ingest()

    assert any(r["source"] == "github_issues" and "7" in r["source_id"] for r in records)
    assert any(r["source"] == "github_prs" and "8" in r["source_id"] for r in records)
    assert all(r["content_hash"] for r in records)


@patch("ev.ingestion.github.httpx.AsyncClient")
async def test_github_ingestion_handles_http_errors(mock_client):
    error_response = MagicMock()
    error_response.status_code = 404
    mock_client.return_value.__aenter__.return_value.get.return_value = error_response

    ingester = GitHubIngestion(Settings(personal_only=True, github_token="ghp_test"))
    ingester.add_repo("satyamdas03", "MissingRepo")
    records = await ingester.ingest()

    assert records == []
