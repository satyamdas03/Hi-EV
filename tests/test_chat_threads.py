"""Tests for persistent chat threads, turns, and REST endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from ev.db.base import Base, SessionLocal, engine
from ev.memory.store import MemoryStore
from ev.server.api import app


@pytest.fixture(autouse=True)
async def chat_thread_tables():
    """Create all tables before each chat thread test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_create_chat_thread():
    async with SessionLocal() as session:
        store = MemoryStore(session)
        thread = await store.create_chat_thread(title="Test thread")
        assert thread.title == "Test thread"
        assert thread.id is not None


async def test_add_and_list_chat_turns():
    async with SessionLocal() as session:
        store = MemoryStore(session)
        thread = await store.create_chat_thread(title="Test thread")
        t1 = await store.add_chat_turn(thread.id, "user", "hello")
        t2 = await store.add_chat_turn(thread.id, "assistant", "hi there", tool_name="chat")
        turns = await store.list_chat_turns(thread.id)
        assert len(turns) == 2
        assert turns[0].id == t1.id
        assert turns[0].ordinal == 0
        assert turns[1].ordinal == 1
        assert turns[1].tool_name == "chat"


async def test_chat_thread_cascades_turns():
    async with SessionLocal() as session:
        store = MemoryStore(session)
        thread = await store.create_chat_thread(title="Test thread")
        await store.add_chat_turn(thread.id, "user", "hello")
        deleted = await store.delete_chat_thread(thread.id)
        assert deleted is True
        turns = await store.list_chat_turns(thread.id)
        assert turns == []


async def test_rest_create_and_list_threads(async_client):
    res = await async_client.post("/threads", json={"title": "API thread"})
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "API thread"

    res = await async_client.get("/threads")
    assert res.status_code == 200
    threads = res.json()
    assert any(t["id"] == body["id"] for t in threads)


async def test_rest_get_thread_with_turns(async_client):
    res = await async_client.post("/threads", json={"title": "API thread"})
    thread_id = res.json()["id"]

    async with SessionLocal() as session:
        store = MemoryStore(session)
        await store.add_chat_turn(thread_id, "user", "hello")
        await store.add_chat_turn(thread_id, "assistant", "hi")

    res = await async_client.get(f"/threads/{thread_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "API thread"
    assert len(body["turns"]) == 2
    assert body["turns"][0]["role"] == "user"
    assert body["turns"][1]["role"] == "assistant"


async def test_rest_rename_and_delete_thread(async_client):
    res = await async_client.post("/threads", json={"title": "Old title"})
    thread_id = res.json()["id"]

    res = await async_client.patch(f"/threads/{thread_id}", json={"title": "New title"})
    assert res.status_code == 200
    assert res.json()["title"] == "New title"

    res = await async_client.delete(f"/threads/{thread_id}")
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    res = await async_client.get(f"/threads/{thread_id}")
    assert res.status_code == 404 or "error" in res.json()
