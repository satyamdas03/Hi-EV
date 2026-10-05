"""VoiceManager orchestrates local STT and TTS for Hi-EV."""

from __future__ import annotations

import logging
from pathlib import Path

from ev.config import Settings, get_settings
from ev.voice.component import BaseSTTBackend, BaseTTSBackend, VoiceBackendError
from ev.voice.io import VoiceIOError, record_until_silence

logger = logging.getLogger(__name__)


class VoiceManager:
    """High-level voice interface: listen, transcribe, synthesize, speak."""

    def __init__(
        self,
        settings: Settings | None = None,
        stt: BaseSTTBackend | None = None,
        tts: BaseTTSBackend | None = None,
    ):
        self.settings = settings or get_settings()
        self.stt = stt or self._default_stt()
        self.tts = tts or self._default_tts()

    def _default_stt(self) -> BaseSTTBackend:
        """Pick the best available STT backend."""
        from ev.voice.stt import FasterWhisperSTT, MockSTT

        name = self.settings.voice_stt_backend or "faster_whisper"
        model_dir = self.settings.voice_model_dir
        try:
            if name == "faster_whisper":
                return FasterWhisperSTT(model_dir=model_dir)
        except VoiceBackendError as exc:
            logger.warning("Preferred STT backend unavailable: %s", exc)
        return MockSTT()

    def _default_tts(self) -> BaseTTSBackend:
        """Pick the best available TTS backend."""
        from ev.voice.tts import KokoroTTS, MockTTS, Pyttsx3TTS

        name = self.settings.voice_tts_backend or "pyttsx3"
        model_dir = self.settings.voice_model_dir
        for backend_cls, backend_name in ((Pyttsx3TTS, "pyttsx3"), (KokoroTTS, "kokoro")):
            if name == backend_name:
                try:
                    return backend_cls(model_dir=model_dir)
                except VoiceBackendError as exc:
                    logger.warning("Preferred TTS backend %s unavailable: %s", backend_name, exc)
        return MockTTS()

    async def listen(self, output_path: Path | None = None) -> Path:
        """Record audio from the microphone until silence."""
        output_path = output_path or Path(self.settings.app_data_dir) / "voice" / "last_input.wav"
        return record_until_silence(output_path)

    async def transcribe(self, audio_path: Path) -> str:
        """Convert an audio file to text."""
        return await self.stt.transcribe(audio_path)

    async def speak(self, text: str, output_path: Path | None = None) -> Path:
        """Synthesize text and play it through the default audio output."""
        output_path = output_path or Path(self.settings.app_data_dir) / "voice" / "last_output.wav"
        path = await self.tts.synthesize(text, output_path)
        try:
            from ev.voice.io import play_wav

            play_wav(path)
        except VoiceIOError as exc:
            logger.warning("Could not play TTS audio: %s", exc)
        return path

    async def listen_and_transcribe(self) -> str:
        """Convenience: record audio and return its transcript."""
        audio_path = await self.listen()
        return await self.transcribe(audio_path)

    async def say(self, text: str) -> Path:
        """Convenience: synthesize and play a response."""
        return await self.speak(text)
