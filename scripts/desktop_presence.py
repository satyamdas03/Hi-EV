"""Single desktop entry point for Hi-EV.

Launches the local daemon, global hotkey listener, system-tray widget, and
optionally opens the HUD in the default browser. This is the script the Windows
installer shortcuts point at.

Run:
    python scripts/desktop_presence.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
import time
import webbrowser
from typing import Any
from urllib.parse import urljoin

import httpx

from ev.config import get_settings

logger = logging.getLogger("ev.desktop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Global voice state. A single VoiceManager instance is created lazily when
# voice is enabled; a busy flag prevents overlapping voice turns from the hotkey.
_voice_manager: Any | None = None
_voice_busy = threading.Event()


def _open_hud(base_url: str) -> None:
    """Open the Hi-EV HUD in the default browser once the daemon is alive."""
    url = urljoin(base_url, "/")
    webbrowser.open(url, new=1)


def _wait_for_daemon(base_url: str, timeout: float = 30.0) -> bool:
    """Poll /health until the daemon responds or timeout elapses."""
    url = urljoin(base_url, "/health")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Daemon health poll failed: %s", exc)
        time.sleep(0.25)
    return False


def _run_daemon(settings) -> None:
    """Run the FastAPI daemon inline using uvicorn."""
    import uvicorn

    host, port = _parse_bind(settings.base_url)
    logger.info("Starting daemon on %s:%s", host, port)
    uvicorn.run(
        "ev.server.api:app",
        host=host,
        port=port,
        log_level="info",
    )


def _parse_bind(base_url: str) -> tuple[str, int]:
    """Parse host:port from EV_BASE_URL."""
    # Typical base_url is http://127.0.0.1:7345
    parts = base_url.rsplit(":", 1)
    host = parts[0].split("/")[-1] or "127.0.0.1"
    port = int(parts[-1].split("/")[0]) if parts[-1].isdigit() else 7345
    return host, port


def _ensure_voice_manager(settings) -> Any | None:
    """Lazily create the VoiceManager when voice is enabled."""
    global _voice_manager
    if _voice_manager is None and settings.voice_enabled:
        try:
            from ev.voice.manager import VoiceManager

            _voice_manager = VoiceManager(settings=settings)
            logger.info(
                "Voice manager ready (stt=%s, tts=%s)",
                _voice_manager.stt.name,
                _voice_manager.tts.name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Voice manager could not start: %s", exc)
    return _voice_manager


async def _async_voice_turn(base_url: str, voice) -> None:
    """One voice turn: listen, transcribe, chat via REST, speak the reply."""
    text = await voice.listen_and_transcribe()
    if not text or not text.strip():
        logger.info("Voice turn: empty transcript")
        return
    logger.info("Voice transcript: %r", text)
    response = httpx.post(
        urljoin(base_url, "/voice/chat"),
        json={"text": text.strip()},
        timeout=120,
    )
    response.raise_for_status()
    reply = response.json().get("response", "")
    if reply:
        logger.info("Voice reply: %r", reply[:200])
        await voice.say(reply)


def _trigger_voice_turn(settings) -> None:
    """Start a voice turn in a background thread if voice is enabled."""
    voice = _ensure_voice_manager(settings)
    if voice is None:
        return
    if _voice_busy.is_set():
        logger.debug("Voice turn already in progress; ignoring hotkey.")
        return
    _voice_busy.set()

    async def _run() -> None:
        try:
            await _async_voice_turn(settings.base_url, voice)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Voice turn failed: %s", exc)
        finally:
            _voice_busy.clear()

    threading.Thread(target=lambda: asyncio.run(_run()), daemon=True).start()


def _run_hotkey(settings) -> None:
    """Run the global hotkey listener inline."""
    if not settings.global_hotkey_enabled:
        logger.info("Global hotkey is disabled (EV_GLOBAL_HOTKEY_ENABLED=false).")
        return

    try:
        from pynput import keyboard
    except ImportError as exc:
        logger.warning("pynput not available; global hotkey disabled (%s)", exc)
        return

    target = _normalize_combo(settings.global_hotkey_combo)
    current: set[str] = set()

    def _on_press(key) -> None:
        token = None
        try:
            token = key.char.lower() if hasattr(key, "char") and key.char else key.name.lower()
        except AttributeError:
            pass
        if token:
            current.add(token)
        if target.issubset(current):
            logger.info("Hotkey %s pressed; focusing EV.", settings.global_hotkey_combo)
            _focus_hiev(settings.base_url)
            _trigger_voice_turn(settings)

    def _on_release(key) -> None:
        token = None
        try:
            token = key.char.lower() if hasattr(key, "char") and key.char else key.name.lower()
        except AttributeError:
            pass
        if token:
            current.discard(token)

    logger.info("Listening for global hotkey: %s", settings.global_hotkey_combo)
    with keyboard.Listener(on_press=_on_press, on_release=_on_release) as listener:
        listener.join()


def _run_tray(settings) -> None:
    """Run the system-tray widget inline."""
    if not settings.tray_widget_enabled:
        logger.info("Tray widget is disabled (EV_TRAY_WIDGET_ENABLED=false).")
        return

    try:
        import pystray
    except ImportError as exc:
        logger.warning("pystray not available; tray widget disabled (%s)", exc)
        return

    def on_open(icon, item):
        threading.Thread(target=_open_hud, args=(settings.base_url,), daemon=True).start()

    def on_focus(icon, item):
        threading.Thread(target=_focus_hiev, args=(settings.base_url,), daemon=True).start()

    def on_check_updates(icon, item):
        threading.Thread(target=_check_updates, args=(settings.base_url,), daemon=True).start()

    def on_exit(icon, item):
        icon.stop()
        _shutdown()

    menu = pystray.Menu(
        pystray.MenuItem("Open HUD", on_open),
        pystray.MenuItem("Focus EV", on_focus),
        pystray.MenuItem("Check for updates", on_check_updates),
        pystray.MenuItem("Exit", on_exit),
    )
    icon = pystray.Icon("hiev", _build_icon(), "Hi-EV", menu)
    logger.info("Starting Hi-EV tray widget.")
    icon.run()


def _normalize_combo(combo: str) -> set[str]:
    """Turn 'ctrl+alt+e' into a canonical set of key tokens."""
    return {token.strip().lower() for token in combo.split("+") if token.strip()}


def _focus_hiev(base_url: str) -> None:
    """POST /focus to the local daemon so every HUD tab/window wakes up."""
    url = urljoin(base_url, "/focus")
    try:
        response = httpx.post(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        logger.info("Focus request sent; clients notified: %s", data.get("clients", 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reach EV daemon at %s: %s", url, exc)


def _check_updates(base_url: str) -> None:
    """Check GitHub for a newer Hi-EV release and log the result."""
    from ev.updater import UpdateChecker

    async def _run() -> None:
        try:
            result = await UpdateChecker().check()
            if result.get("error"):
                logger.warning("Update check failed: %s", result["error"])
            elif result["update_available"]:
                logger.info(
                    "Update available: %s → %s. Installer: %s",
                    result["current"],
                    result["latest"],
                    result["url"],
                )
            else:
                logger.info("Hi-EV is up to date (%s).", result["current"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Update check failed: %s", exc)

    threading.Thread(target=lambda: asyncio.run(_run()), daemon=True).start()


def _build_icon(size: int = 64):
    """Build a simple cyan-on-black EV icon using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    margin = 4
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=12,
        fill=(25, 196, 196, 255),
    )
    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "EV", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - 2
    draw.text((x, y), "EV", font=font, fill=(5, 10, 14, 255))
    return image


_shutdown_event = threading.Event()


def _shutdown(signum=None, frame=None) -> None:
    logger.info("Shutting down Hi-EV desktop presence.")
    _shutdown_event.set()


def main() -> int:
    settings = get_settings()
    base_url = settings.base_url

    logger.info("Starting Hi-EV desktop presence.")
    logger.info("Daemon URL: %s", base_url)

    daemon_thread = threading.Thread(target=_run_daemon, args=(settings,), daemon=True)
    daemon_thread.start()

    if not _wait_for_daemon(base_url, timeout=30.0):
        logger.error("Daemon did not become ready within 30 seconds.")
        return 1

    logger.info("Daemon ready.")

    hotkey_thread = threading.Thread(target=_run_hotkey, args=(settings,), daemon=True)
    hotkey_thread.start()

    tray_thread = threading.Thread(target=_run_tray, args=(settings,), daemon=True)
    tray_thread.start()

    if settings.desktop_auto_open_hud:
        threading.Thread(target=_open_hud, args=(base_url,), daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        while not _shutdown_event.is_set():
            if not daemon_thread.is_alive():
                logger.error("Daemon thread exited unexpectedly.")
                return 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        _shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
