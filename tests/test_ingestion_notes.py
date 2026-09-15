"""Tests for the notes vault ingestion source."""

import tempfile
from pathlib import Path

import pytest

from ev.config import Settings
from ev.ingestion.notes import NotesIngestion
from ev.security.boundary import PersonalOnlyError


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
        assert all(r["source_id"] for r in records)
        assert all(r["content_hash"] for r in records)
        assert all(r["privacy_level"] == "personal" for r in records)


def test_notes_ingestion_refuses_non_personal_mode():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "note.md").write_text("personal note")
        with pytest.raises(PersonalOnlyError):
            NotesIngestion(Settings(notes_path=root, personal_only=False))


def test_notes_ingestion_skips_blocklisted_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "robocad.md").write_text("# RoboCAD")
        (root / "financialsimplicity.md").write_text("work stuff")
        ingester = NotesIngestion(Settings(notes_path=root, personal_only=True))
        records = ingester.ingest()
        assert len(records) == 1
        assert records[0]["source_id"].endswith("robocad.md")
