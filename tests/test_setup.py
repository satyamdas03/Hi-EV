"""Tests for the first-run setup wizard backend."""

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


def _fresh_settings(tmp_path: Path, **overrides):
    """Return an isolated Settings object with no API keys and a temp data dir."""
    from ev.config import Settings

    defaults = {
        "app_data_dir": tmp_path,
        "env_file_path": tmp_path / ".env",
        "database_url": f"sqlite+aiosqlite:///{tmp_path / 'hiev.db'}",
        "nvidia_api_key": None,
        "anthropic_api_key": None,
        "openai_api_key": None,
        "github_token": None,
        "notes_path": tmp_path / "notes_missing",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def temp_env_dir(tmp_path):
    """Provide an isolated app data directory and patch config to use it."""
    env_path = tmp_path / ".env"
    settings = _fresh_settings(tmp_path, env_file_path=env_path)

    with (
        patch("ev.server.setup.get_settings", return_value=settings),
        patch("ev.server.setup._env_file_path", return_value=env_path),
        patch("ev.config.get_settings", return_value=settings),
    ):
        yield env_path


async def test_setup_status_needs_setup_when_env_missing(temp_env_dir, tmp_path):
    from ev.server.api import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/setup")
    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is True
    assert "env_file" in data["missing"]
    assert "notes_path" in data["missing"]
    assert "llm_key" in data["missing"]
    assert "defaults" in data


async def test_setup_status_ready_after_apply(temp_env_dir, tmp_path):
    from ev.server.api import app
    from ev.server.setup import SetupRequest, apply_setup

    notes = tmp_path / "notes"
    notes.mkdir()
    req = SetupRequest(
        notes_path=str(notes),
        llm_provider="nvidia",
        nvidia_api_key="nvapi-test",
    )
    apply_setup(req)

    # Re-point settings at the freshly written env file so the status check sees it.
    settings = _fresh_settings(
        tmp_path,
        env_file_path=temp_env_dir,
        notes_path=notes,
        nvidia_api_key="nvapi-test",
    )
    with (
        patch("ev.server.setup.get_settings", return_value=settings),
        patch("ev.server.setup._env_file_path", return_value=temp_env_dir),
        patch("ev.config.get_settings", return_value=settings),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/setup")

    assert response.status_code == 200
    data = response.json()
    assert data["needs_setup"] is False
    assert data["env_exists"] is True


async def test_setup_apply_writes_env_file(temp_env_dir, tmp_path):
    from ev.server.api import app

    notes = tmp_path / "notes"
    payload = {
        "notes_path": str(notes),
        "llm_provider": "anthropic",
        "llm_model": "claude-3-5-sonnet-20241022",
        "anthropic_api_key": "sk-ant-test",
        "blocked_handles": ["workhandle"],
        "blocked_domains": ["work.example.com"],
        "quiet_start": "21:00",
        "quiet_end": "07:00",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/setup", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["restart_required"] is True
    assert data["env_path"] == str(temp_env_dir)

    env_text = temp_env_dir.read_text()
    assert "EV_NOTES_PATH=" + str(notes) in env_text
    assert "EV_ANTHROPIC_API_KEY=sk-ant-test" in env_text
    assert 'EV_BLOCKED_HANDLES=["workhandle"]' in env_text
    assert 'EV_BLOCKED_DOMAINS=["work.example.com"]' in env_text


async def test_setup_apply_validates_notes_path(temp_env_dir):
    from ev.server.api import app

    # Use a non-existent Windows drive letter so mkdir fails for real.
    payload = {
        "notes_path": "Z:\\nonexistent\\notes_path",
        "llm_provider": "nvidia",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/setup", json=payload)

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "notes path" in detail or "could not create" in detail


async def test_setup_apply_rejects_invalid_provider(temp_env_dir, tmp_path):
    from ev.server.api import app

    notes = tmp_path / "notes"
    payload = {
        "notes_path": str(notes),
        "llm_provider": "invalid-provider",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/setup", json=payload)

    assert response.status_code == 422
