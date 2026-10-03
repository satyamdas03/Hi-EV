"""Voice backend base classes and registries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator

from ev.core import registry


class BaseSTTBackend(ABC):
    """Speech-to-text backend."""

    name: str

    @abstractmethod
    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Return the transcript for an audio file."""


class BaseTTSBackend(ABC):
    """Text-to-speech backend."""

    name: str

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path | None = None, voice: str | None = None) -> Path:
        """Synthesize text to an audio file and return its path."""


# STT/TTS have their own registries within the global registry dict.
registry["stt"] = type(registry["tool"])("stt")
registry["tts"] = type(registry["tool"])("tts")
