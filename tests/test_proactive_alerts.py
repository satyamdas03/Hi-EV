"""Tests for proactive alert push, morning brief scheduler, and Telegram relay."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.server.api import _alert_loop
from ev.server.telegram import TelegramRelay


@pytest.fixture(autouse=True)
async def proactive_tables():
    """Create all tables before each proactive test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def quiet_settings():
    """Return settings with quiet hours in the past so loops don't skip."""
    from ev.config import Settings

    return Settings(
        proactive_alerts_enabled=True,
        morning_brief_enabled=True,
        morning_brief_time="08:00",
        alert_interval_sec=0,
        quiet_start="00:00",
        quiet_end="00:01",
        alert_window_hours=72,
    )


async def test_alert_loop_pushes_to_websockets(quiet_settings):
    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.upsert_deadlines([
            {
                "title": "Urgent review",
                "due_date": datetime.now(UTC) + timedelta(hours=2),
                "source": "calendar",
                "source_id": "urgent-1",
                "project_name": "robocad",
            }
        ])

    ws = MagicMock()
    ws.send_json = AsyncMock()
    app_state = type("State", (), {"active_websockets": {ws}, "_last_brief_date": None})()

    with patch("ev.server.api.app") as mock_app:
        mock_app.state = app_state
        # Run one iteration by cancelling after a short delay.
        task = asyncio.create_task(_alert_loop(quiet_settings))
        await asyncio.sleep(0.15)
        task.cancel()
        await task

    assert ws.send_json.await_count >= 1
    payload = ws.send_json.await_args.args[0]
    assert payload["type"] == "alert"
    assert payload["category"] == "deadline"


async def test_telegram_relay_skips_when_disabled():
    from ev.config import Settings

    settings = Settings(telegram_enabled=False)
    with patch("ev.server.telegram.get_settings", return_value=settings):
        relay = TelegramRelay()
        result = await relay.send("hello")
        assert result["sent"] is False
        assert result["reason"] == "not_configured"


async def test_telegram_relay_formats_alert():
    from pydantic import SecretStr

    relay = TelegramRelay()
    relay.enabled = True
    relay.token = SecretStr("bot_token")
    relay.chat_id = "chat123"

    response = MagicMock()
    response.json.return_value = {"ok": True, "result": {"message_id": 42}}

    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client):
        result = await relay.alert("Urgent", "2 deadlines", [{"title": "Review"}])
        assert result["sent"] is True
        assert result["message_id"] == 42
        call_args = client.post.await_args
        assert "sendMessage" in call_args.args[0]
