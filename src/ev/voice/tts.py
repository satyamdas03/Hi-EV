"""Text-to-speech backends for Hi-EV."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ev.core import register
from ev.voice.component import BaseTTSBackend, VoiceBackendError

logger = logging.getLogger(__name__)


@register("tts", "kokoro")
class KokoroTTS(BaseTTSBackend):
    """Local TTS using Kokoro.

    Requires the `kokoro` package and a voice model download.
    """

    name = "kokoro"

    def __init__(self, voice: str = "af", lang: str = "en-us", model_dir: Path | str | None = None):
        self.voice = voice
        self.lang = lang
        self.model_dir = Path(model_dir) if model_dir else None
        self._pipeline: Any | None = None

    def _load(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline  # type: ignore[import-untyped]
            except ImportError as exc:
                raise VoiceBackendError("kokoro is not installed") from exc
            # Kokoro downloads voices on demand; ensure the cache directory exists.
            if self.model_dir:
                self.model_dir.mkdir(parents=True, exist_ok=True)
            self._pipeline = KPipeline(lang_code=self.lang)
        return self._pipeline

    async def synthesize(self, text: str, output_path: Path | None = None, voice: str | None = None) -> Path:
        import soundfile as sf  # type: ignore[import-untyped]

        pipeline = self._load()
        output_path = output_path or Path("tmp_tts.wav")
        generator = pipeline(text, voice=voice or self.voice)
        # Kokoro yields (gs, ps, audio) tuples; concatenate audio arrays.
        audio_segments = []
        for _, _, audio in generator:
            audio_segments.append(audio)
        if not audio_segments:
            raise VoiceBackendError("Kokoro produced no audio")
        import numpy as np

        full_audio = np.concatenate(audio_segments)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), full_audio, 24000)
        return output_path


@register("tts", "pyttsx3")
class Pyttsx3TTS(BaseTTSBackend):
    """Cross-platform system TTS fallback using pyttsx3."""

    name = "pyttsx3"

    def __init__(self, model_dir: Path | str | None = None) -> None:
        try:
            import pyttsx3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise VoiceBackendError("pyttsx3 is not installed") from exc
        self.engine = pyttsx3.init()
        self.model_dir = Path(model_dir) if model_dir else None

    async def synthesize(self, text: str, output_path: Path | None = None, voice: str | None = None) -> Path:
        output_path = output_path or Path("tmp_tts.wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine.save_to_file(text, str(output_path))
        self.engine.runAndWait()
        return output_path


@register("tts", "mock")
class MockTTS(BaseTTSBackend):
    """TTS backend for tests / fallback that writes a tiny silent WAV."""

    name = "mock"

    async def synthesize(self, text: str, output_path: Path | None = None, voice: str | None = None) -> Path:
        import numpy as np

        output_path = output_path or Path("tmp_tts.wav")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        silence = np.zeros(16000, dtype="float32")
        try:
            import soundfile as sf  # type: ignore[import-untyped]

            sf.write(str(output_path), silence, 16000)
        except ImportError:
            from ev.voice.io import _write_wav_with_wave

            _write_wav_with_wave(output_path, silence, 16000)
        return output_path


