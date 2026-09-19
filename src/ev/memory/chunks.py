"""Document chunking pipeline for semantic memory.

Turns long-form text (notes, emails, transcripts, user memories) into
fixed-size overlapping chunks suitable for embedding and retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    """One semantic chunk ready for storage."""

    source: str
    source_id: str
    chunk_index: int
    text: str
    project_name: str | None = None
    trusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_id": self.source_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "project_name": self.project_name,
            "trusted": self.trusted,
        }


class Chunker:
    """Deterministic text splitter with paragraph/sentence/word fallbacks."""

    def __init__(self, max_chars: int = 512, overlap_chars: int = 64):
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be in [0, max_chars)")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def split(
        self,
        text: str,
        source: str,
        source_id: str,
        project_name: str | None = None,
        trusted: bool = True,
    ) -> list[TextChunk]:
        """Split *text* into chunks and assign (source, source_id, chunk_index)."""
        if not text or not text.strip():
            return []

        normalized = self._normalize(text)
        segments = self._segment(normalized)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            # If a single segment exceeds max_chars, split it further.
            while len(segment) > self.max_chars:
                piece = self._trim_to_word_boundary(segment, self.max_chars)
                if not piece:
                    piece = segment[: self.max_chars]
                chunks.append(piece)
                segment = segment[len(piece) :].lstrip()
                if not segment:
                    break
            if not segment:
                continue

            delimiter = " " if current else ""
            added_len = len(delimiter) + len(segment)
            if current_len + added_len <= self.max_chars:
                current.append(segment)
                current_len += added_len
            else:
                chunks.append(" ".join(current))
                overlap = self._overlap(current)
                current = [overlap, segment] if overlap else [segment]
                current_len = len(" ".join(current))

        if current:
            chunks.append(" ".join(current))

        return [
            TextChunk(
                source=source,
                source_id=source_id,
                chunk_index=idx,
                text=chunk.strip(),
                project_name=project_name,
                trusted=trusted,
            )
            for idx, chunk in enumerate(chunks)
            if chunk.strip()
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        # Collapse excessive whitespace but keep paragraph structure.
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def _segment(self, text: str) -> list[str]:
        """Prefer paragraphs, then sentences if paragraphs are too large."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return []
        # If every paragraph fits, use them.
        if all(len(p) <= self.max_chars for p in paragraphs):
            return paragraphs

        # Otherwise split by sentences to get finer granularity.
        sentences: list[str] = []
        for para in paragraphs:
            # Simple sentence split on period/question/exclamation followed by space or newline.
            parts = re.split(r"(?<=[.?!])\s+", para)
            for part in parts:
                part = part.strip()
                if part:
                    sentences.append(part)
        return sentences

    def _overlap(self, current: list[str]) -> str:
        """Return a trailing overlap string from the previous chunk."""
        if not current or self.overlap_chars <= 0:
            return ""
        previous = " ".join(current)
        overlap = previous[-self.overlap_chars :].lstrip()
        # Avoid cutting mid-word at the start.
        if " " in overlap:
            overlap = overlap[overlap.find(" ") + 1 :]
        return overlap.strip()

    @staticmethod
    def _trim_to_word_boundary(text: str, limit: int) -> str:
        """Return the largest prefix of *text* under *limit* that ends on a word boundary."""
        if len(text) <= limit:
            return text
        cut = text[:limit]
        # Find the last space in the cut.
        last_space = cut.rfind(" ")
        if last_space > 0:
            return cut[:last_space]
        return cut


def chunk_ingest_records(
    records: list[dict[str, Any]],
    chunker: Chunker | None = None,
) -> list[dict[str, Any]]:
    """Translate raw Ingest records into DocumentChunk dicts.

    Only records with meaningful long-form content are chunked. Short or
    structured records (e.g., single calendar deadlines) are ignored because
    they already have dedicated tables.
    """
    chunker = chunker or Chunker()
    chunks: list[dict[str, Any]] = []

    long_form_sources = {
        "notes",
        "gmail_messages",
        "github_issues",
        "github_prs",
        "transcript",
        "user_memory",
    }

    for record in records:
        source = record.get("source", "")
        if source not in long_form_sources:
            continue
        content = record.get("content") or ""
        if not content.strip():
            continue
        project_tag = record.get("project_tag") or record.get("project_name")
        trusted = record.get("trusted", True)
        for chunk in chunker.split(
            content,
            source=source,
            source_id=record.get("source_id", ""),
            project_name=project_tag,
            trusted=trusted,
        ):
            chunks.append(chunk.to_dict())

    return chunks
