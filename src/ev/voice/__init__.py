"""Hi-EV local voice pipeline.

Provides pluggable speech-to-text and text-to-speech backends. The pipeline is
optional: if the required third-party packages are not installed, voice falls
back to browser/cloud STT/TTS gracefully.
"""

from ev.voice.manager import VoiceManager

__all__ = ["VoiceManager"]
