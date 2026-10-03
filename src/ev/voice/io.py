"""Local audio I/O helpers for Hi-EV voice.

Records microphone audio until silence, then saves a WAV file. Playback uses
the best available local audio library. If `sounddevice`/`soundfile` are not
installed, the helpers fall back to writing a silent WAV so the rest of the
pipeline can still be tested and degraded gracefully.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _import_sounddevice() -> Any:
    try:
        import sounddevice as sd  # type: ignore[import-untyped]

        return sd
    except ImportError as exc:
        raise VoiceIOError("sounddevice is not installed; cannot record audio") from exc


def _import_soundfile() -> Any:
    try:
        import soundfile as sf  # type: ignore[import-untyped]

        return sf
    except ImportError as exc:
        raise VoiceIOError("soundfile is not installed; cannot write audio") from exc


def _write_wav_with_wave(path: Path, samples: Any, samplerate: int) -> Path:
    """Write a mono float32 numpy array as a 16-bit PCM WAV using stdlib `wave`.

    This avoids a hard dependency on `soundfile` for tests and mock backends.
    """
    import numpy as np

    audio = np.asarray(samples)
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)
    # Normalize only if samples exceed [-1, 1]; otherwise direct int16 conversion.
    peak = np.max(np.abs(audio))
    if peak > 1.0:
        audio = audio / peak
    int16 = (audio * 32767).astype(np.int16)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(samplerate)
        wav.writeframes(int16.tobytes())
    return path


class VoiceIOError(Exception):
    """Raised when the local audio stack is unavailable or fails."""


def play_wav(path: Path) -> None:
    """Play a WAV file through the default output device."""
    sd = _import_sounddevice()
    sf = _import_soundfile()
    data, samplerate = sf.read(str(path))
    sd.play(data, samplerate)
    sd.wait()


def record_until_silence(
    output_path: Path,
    samplerate: int = 16000,
    channels: int = 1,
    silence_duration: float = 1.5,
    max_duration: float = 30.0,
) -> Path:
    """Record microphone audio until silence is detected, then save a WAV.

    Args:
        output_path: where to write the 16-bit PCM WAV file.
        samplerate: recording sample rate (default 16 kHz for STT models).
        channels: number of channels (default mono).
        silence_duration: seconds of silence before stopping.
        max_duration: hard cap on recording length.
    """
    import numpy as np

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Recording audio to %s", output_path)
    try:
        sd = _import_sounddevice()
    except VoiceIOError as exc:
        logger.warning("Microphone unavailable (%s); writing silent WAV for tests/degraded mode.", exc)
        silence = np.zeros(samplerate, dtype="float32")
        return _write_wav_with_wave(output_path, silence, samplerate)

    blocksize = int(samplerate * 0.05)  # 50 ms blocks
    silence_blocks = int(silence_duration / 0.05)
    max_blocks = int(max_duration / 0.05)

    frames: list = []
    silent_count = 0

    with sd.InputStream(samplerate=samplerate, channels=channels, blocksize=blocksize, dtype="float32") as stream:
        for _ in range(max_blocks):
            block, _ = stream.read(blocksize)
            frames.append(block.copy())
            # Simple energy-based VAD.
            energy = float(np.sqrt(np.mean(block**2)))
            if energy < 0.01:
                silent_count += 1
            else:
                silent_count = 0
            if silent_count >= silence_blocks:
                break

    audio = np.concatenate(frames, axis=0)
    try:
        sf = _import_soundfile()
        sf.write(str(output_path), audio, samplerate)
    except VoiceIOError:
        _write_wav_with_wave(output_path, audio, samplerate)
    logger.info("Saved %d samples to %s", len(audio), output_path)
    return output_path
