"""Single desktop entry point for Hi-EV.

Launches the local daemon, global hotkey listener, system-tray widget, and
optionally opens the HUD in the default browser. This is the script the Windows
installer shortcuts point at.

Run:
    python scripts/desktop_presence.py
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
import webbrowser
from urllib.parse import urljoin

import httpx

from ev.config import get_settings

logger = logging.getLogger("ev.desktop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


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

    def on_exit(icon, item):
        icon.stop()
        _shutdown()

    menu = pystray.Menu(
        pystray.MenuItem("Open HUD", on_open),
        pystray.MenuItem("Focus EV", on_focus),
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
