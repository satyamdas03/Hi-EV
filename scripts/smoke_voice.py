#!/usr/bin/env python3
"""Smoke test for the Hi-EV voice endpoints.

Expects the daemon to be running on http://127.0.0.1:7345.
Exercises /voice/settings, /voice/speak, and /voice/transcribe with a small
valid WAV.
"""

from __future__ import annotations

import io
import sys
import wave

import requests

BASE_URL = "http://127.0.0.1:7345"


def _make_wav() -> bytes:
    """Return a tiny valid mono WAV in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 0.25 seconds of silence
        wf.writeframes(b"\x00\x00" * 4000)
    return buf.getvalue()


def main() -> int:
    try:
        settings = requests.get(f"{BASE_URL}/voice/settings", timeout=10)
        settings.raise_for_status()
        print("settings:", settings.json())
    except requests.RequestException as exc:
        print(f"settings failed: {exc}")
        return 1

    try:
        speak = requests.post(
            f"{BASE_URL}/voice/speak",
            json={"text": "Hi EV voice smoke test."},
            timeout=30,
        )
        speak.raise_for_status()
        print("speak:", speak.json())
    except requests.RequestException as exc:
        print(f"speak failed: {exc}")
        return 1

    wav_bytes = _make_wav()
    try:
        transcribe = requests.post(
            f"{BASE_URL}/voice/transcribe",
            files={"audio": ("smoke.wav", io.BytesIO(wav_bytes), "audio/wav")},
            timeout=60,
        )
        transcribe.raise_for_status()
        print("transcribe:", transcribe.json())
    except requests.RequestException as exc:
        print(f"transcribe failed: {exc}")
        return 1

    print("Voice smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
