"""System-tray widget skeleton for Hi-EV.

Shows a small icon in the system tray with EV status and a menu to open the
HUD, trigger focus, or exit. This is an optional Phase D desktop-presence
component; it runs as its own process and talks to the local daemon over HTTP.

Dependencies (optional desktop group):
    pip install pystray Pillow httpx

Run:
    python scripts/tray_widget.py
"""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from urllib.parse import urljoin

from ev.config import get_settings

logger = logging.getLogger("ev.tray")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _focus_hiev() -> None:
    """POST /focus to the local daemon so every HUD tab/window wakes up."""
    import httpx

    settings = get_settings()
    url = urljoin(settings.base_url, "/focus")
    try:
        response = httpx.post(url, timeout=5)
        response.raise_for_status()
        logger.info("Focus request sent.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reach EV daemon at %s: %s", url, exc)


def _open_hud() -> None:
    """Open the Hi-EV HUD in the default browser."""
    settings = get_settings()
    url = urljoin(settings.base_url, "/")
    webbrowser.open(url, new=1)


def _build_icon(size: int = 64):
    """Build a simple cyan-on-black EV icon using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    # Draw a rounded cyan square background.
    margin = 4
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=12,
        fill=(25, 196, 196, 255),
    )
    # Draw 'EV' text in black.
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


def main() -> int:
    settings = get_settings()
    if not settings.tray_widget_enabled:
        logger.info("Tray widget is disabled (EV_TRAY_WIDGET_ENABLED=false).")
        return 0

    try:
        import pystray
    except ImportError as exc:
        logger.error(
            "pystray and Pillow are required for the tray widget. "
            "Install them with: pip install pystray Pillow (%s)",
            exc,
        )
        return 1

    def on_open(icon, item):
        threading.Thread(target=_open_hud, daemon=True).start()

    def on_focus(icon, item):
        threading.Thread(target=_focus_hiev, daemon=True).start()

    def on_exit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open HUD", on_open),
        pystray.MenuItem("Focus EV", on_focus),
        pystray.MenuItem("Exit", on_exit),
    )
    icon = pystray.Icon("hiev", _build_icon(), "Hi-EV", menu)
    logger.info("Starting Hi-EV tray widget.")
    icon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
