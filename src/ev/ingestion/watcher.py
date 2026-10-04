"""File-system watcher for the Hi-EV memory vault.

Watches the user's notes path and active project directories for create,
modify, move, and delete events. Debounces and coalesces events, then runs
incremental ingestion so semantic memory stays fresh without waiting for the
background scheduler poll.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from pathlib import Path
from typing import Any

from watchdog.events import (
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from ev.config import Settings
from ev.db.base import SessionLocal
from ev.db.models import Ingest
from ev.memory.chunks import chunk_ingest_records
from ev.memory.store import MemoryStore

logger = logging.getLogger(__name__)

# File types we care about for incremental ingestion.
WATCHED_SUFFIXES = {".md"}

# How long to wait after the last event for a path before running ingestion.
DEBOUNCE_SECONDS = 2.0

# Give the watchdog observer thread a moment to register with the OS before
# callers start writing files (eliminates flaky misses on Windows tests).
STARTUP_DELAY_SECONDS = 0.5


class VaultEventHandler(FileSystemEventHandler):
    """Collect filesystem events and schedule debounced ingestion."""

    def __init__(
        self,
        queue: asyncio.Queue[tuple[str, Path | None]],
        loop: asyncio.AbstractEventLoop,
    ):
        self._queue = queue
        self._loop = loop

    def on_any_event(self, event: FileSystemEvent) -> None:
        # Skip transient / noisy events.
        if event.event_type in {"opened", "closed"}:
            return
        if getattr(event, "is_directory", False):
            return

        path = self._path_from_event(event)
        if path is None:
            return
        if path.suffix.lower() not in WATCHED_SUFFIXES:
            return

        action = self._action_from_event(event)
        # The watchdog observer runs in its own thread, so enqueue into the
        # asyncio loop thread-safely to wake the debounce task.
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, (action, path))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not queue watcher event for %s: %s", path, exc)

    @staticmethod
    def _path_from_event(event: FileSystemEvent) -> Path | None:
        if isinstance(event, (FileMovedEvent, DirMovedEvent)):
            return Path(event.dest_path)
        if hasattr(event, "src_path") and event.src_path:
            return Path(event.src_path)
        return None

    @staticmethod
    def _action_from_event(event: FileSystemEvent) -> str:
        if isinstance(event, FileDeletedEvent):
            return "deleted"
        if isinstance(event, (FileMovedEvent, DirMovedEvent)) and hasattr(
            event, "dest_path"
        ):
            return "moved"
        if isinstance(event, FileCreatedEvent):
            return "created"
        return "modified"


class VaultWatcher:
    """Watch configured paths and run incremental ingestion."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._observer: Observer | None = None
        self._event_queue: asyncio.Queue[tuple[str, Path | None]] = asyncio.Queue()
        self._debounce_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start watching the configured paths."""
        if self._running:
            return
        self._running = True

        paths = self._watch_paths()
        if not paths:
            logger.info("No paths configured for file-system watcher; skipping")
            return

        self._observer = Observer()
        handler = VaultEventHandler(self._event_queue, asyncio.get_running_loop())
        for path in paths:
            if path.exists() and path.is_dir():
                try:
                    self._observer.schedule(handler, str(path), recursive=True)
                    logger.info("Watching path: %s", path)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not watch %s: %s", path, exc)

        self._observer.start()
        await asyncio.sleep(STARTUP_DELAY_SECONDS)
        self._debounce_task = asyncio.create_task(self._debounce_loop())

    async def stop(self) -> None:
        """Stop watching and clean up tasks."""
        self._running = False
        if self._debounce_task:
            self._debounce_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._debounce_task
            self._debounce_task = None
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error stopping watcher: %s", exc)
            self._observer = None

    def _watch_paths(self) -> list[Path]:
        """Return unique directories to watch from settings."""
        candidates: list[Path | None] = [
            self.settings.notes_path if self.settings.notes_path else None,
            self.settings.robocad_path,
            self.settings.learningrobotics_path,
            self.settings.hiev_path,
        ]
        seen: set[Path] = set()
        paths: list[Path] = []
        for candidate in candidates:
            if candidate is None:
                continue
            path = Path(candidate)
            if not path.exists() or not path.is_dir():
                continue
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
        return paths

    async def _debounce_loop(self) -> None:
        """Collect events, debounce per path, and run incremental ingestion."""
        pending: dict[Path | None, str] = {}
        while self._running:
            try:
                action, path = await asyncio.wait_for(
                    self._event_queue.get(), timeout=DEBOUNCE_SECONDS
                )
                pending[path] = action
            except TimeoutError:
                if pending:
                    await self._ingest_pending(pending)
                    pending = {}
                continue
            except asyncio.CancelledError:
                break

        # Drain remaining events on shutdown.
        while not self._event_queue.empty():
            try:
                action, path = self._event_queue.get_nowait()
                pending[path] = action
            except asyncio.QueueEmpty:
                break
        if pending:
            await self._ingest_pending(pending)

    async def _ingest_pending(self, pending: dict[Path | None, str]) -> None:
        """Process the coalesced set of paths."""
        if not pending:
            return

        deleted: set[Path] = set()
        changed_or_created: set[Path] = set()
        for path, action in pending.items():
            if path is None:
                continue
            if action == "deleted":
                deleted.add(path)
            else:
                changed_or_created.add(path)

        # Only re-ingest files that still exist.
        to_ingest = {p for p in changed_or_created if p.exists()}
        to_delete = {p for p in deleted if not p.exists()}

        try:
            async with SessionLocal() as session:
                store = MemoryStore(session)
                await self._delete_paths(store, to_delete)
                await self._ingest_paths(store, to_ingest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Incremental ingestion failed: %s", exc)

    @staticmethod
    async def _delete_paths(store: MemoryStore, paths: set[Path]) -> None:
        """Remove vector chunks and Ingest rows for deleted note files."""
        from sqlalchemy import select

        for path in paths:
            source_id = str(path)
            deleted_chunks = await store.delete_document_chunks("notes", source_id)
            result = await store.session.execute(
                select(Ingest).where(
                    Ingest.source == "notes", Ingest.source_id == source_id
                )
            )
            ingest_rows = result.scalars().all()
            for row in ingest_rows:
                await store.session.delete(row)
            if ingest_rows:
                await store.session.commit()
            logger.info(
                "Removed note: %s (chunks=%d, ingest_rows=%d)",
                source_id,
                deleted_chunks,
                len(ingest_rows),
            )

    @staticmethod
    async def _ingest_paths(store: MemoryStore, paths: set[Path]) -> None:
        """Ingest a set of markdown files directly without re-scanning the vault."""
        if not paths:
            return

        records: list[dict[str, Any]] = []
        for path in paths:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read %s: %s", path, exc)
                continue
            records.append(
                {
                    "source": "notes",
                    "source_id": str(path),
                    "content_hash": _hash(content),
                    "content": content,
                    "project_tag": _guess_project_tag(content, str(path)),
                    "privacy_level": "personal",
                    "trusted": True,
                }
            )

        if not records:
            return

        await store.upsert_ingest(records)
        await store.upsert_document_chunks(chunk_ingest_records(records))
        logger.info("Incrementally ingested %d note file(s)", len(records))


def _hash(content: str) -> str:
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _guess_project_tag(content: str, rel_path: str) -> str | None:
    lower = (content + " " + rel_path).lower()
    for keyword in ["robocad", "learningrobotics", "neuralquant", "hi-ev"]:
        if keyword in lower:
            return keyword
    return None
