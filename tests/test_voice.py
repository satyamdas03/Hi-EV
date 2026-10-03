"""Tests for the Hi-EV voice pipeline (mock backends; no heavy model downloads)."""

from pathlib import Path

import pytest

from ev.voice.component import BaseSTTBackend, BaseTTSBackend
from ev.voice.manager import VoiceManager
from ev.voice.stt import MockSTT
from ev.voice.tts import MockTTS


@pytest.mark.anyio
async def test_voice_manager_mock_listen_and_transcribe(tmp_path):
    manager = VoiceManager(stt=MockSTT("hello world"), tts=MockTTS())
    text = await manager.listen_and_transcribe()
    assert text == "hello world"


@pytest.mark.anyio
async def test_voice_manager_speak_writes_wav(tmp_path):
    manager = VoiceManager(stt=MockSTT(), tts=MockTTS())
    out = tmp_path / "out.wav"
    path = await manager.speak("hi", output_path=out)
    assert path == out
    assert out.exists()


def test_stt_registry_has_mock_and_faster_whisper():
    from ev.core import registry

    names = registry["stt"].list()
    assert "mock" in names
    assert "faster_whisper" in names


def test_tts_registry_has_mock_kokoro_pyttsx3():
    from ev.core import registry

    names = registry["tts"].list()
    assert "mock" in names
    assert "kokoro" in names
    assert "pyttsx3" in names
