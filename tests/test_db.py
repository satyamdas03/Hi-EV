import pytest
from sqlalchemy import select

from ev.db.base import Base, SessionLocal, engine
from ev.db.models import Event, Ingest, Project


@pytest.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_create_project(db_session):
    p = Project(
        name="RoboCAD",
        repo_url="https://github.com/satyamdas03/RoboCAD",
        current_phase="Phase 29",
    )
    db_session.add(p)
    await db_session.commit()
    result = await db_session.execute(select(Project).where(Project.name == "RoboCAD"))
    assert result.scalar_one().current_phase == "Phase 29"
