"""Speech-to-text backends for Hi-EV."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ev.core import register
from ev.voice.component import BaseSTTBackend, VoiceBackendError

logger = logging.getLogger(__name__)


@register("stt", "faster_whisper")
class FasterWhisperSTT(BaseSTTBackend):
    """Local STT using faster-whisper.

    Requires the `faster-whisper` package and a model download. The model is
    loaded lazily on first use.
    """

    name = "faster_whisper"

    def __init__(
        self,
        model_size: str = "tiny",
        device: str = "cpu",
        model_dir: Path | str | None = None,
    ):
        self.model_size = model_size
        self.device = device
        self.model_dir = Path(model_dir) if model_dir else None
        self._model: Any | None = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise VoiceBackendError("faster-whisper is not installed") from exc
            if self.model_dir:
                self.model_dir.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                download_root=str(self.model_dir) if self.model_dir else None,
            )
        return self._model

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        model = self._load()
        segments, _ = model.transcribe(str(audio_path), language=language)
        return " ".join(segment.text for segment in segments).strip()


@register("stt", "mock")
class MockSTT(BaseSTTBackend):
    """STT backend for tests / fallback that returns a fixed or configured text."""

    name = "mock"

    def __init__(self, fixed_text: str = "mock transcript"):
        self.fixed_text = fixed_text

    async def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        logger.debug("MockSTT transcribed %s", audio_path)
        return self.fixed_text


