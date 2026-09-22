"""Global hotkey listener for Hi-EV.

Listens for the configured key combination (default Ctrl+Alt+E) and asks the
local EV daemon to focus all connected HUD clients. This is a separate
lightweight process so the main daemon does not need desktop/UI privileges.

Dependencies (optional desktop group):
    pip install pynput httpx

Run:
    python scripts/global_hotkey.py
"""

from __future__ import annotations

import logging
import sys
from urllib.parse import urljoin

from ev.config import get_settings

logger = logging.getLogger("ev.hotkey")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _normalize_combo(combo: str) -> set[str]:
    """Turn 'ctrl+alt+e' into a canonical set of key tokens."""
    return {token.strip().lower() for token in combo.split("+") if token.strip()}


def _focus_hiev() -> None:
    """POST /focus to the local daemon so every HUD tab/window wakes up."""
    import httpx

    settings = get_settings()
    # Default daemon URL; override with EV_BASE_URL if the daemon is not on 8000.
    base_url = getattr(settings, "base_url", "http://127.0.0.1:8000")
    url = urljoin(base_url, "/focus")
    try:
        response = httpx.post(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        logger.info("Focus request sent; clients notified: %s", data.get("clients", 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reach EV daemon at %s: %s", url, exc)


def main() -> int:
    settings = get_settings()
    if not settings.global_hotkey_enabled:
        logger.info("Global hotkey is disabled (EV_GLOBAL_HOTKEY_ENABLED=false).")
        return 0

    try:
        from pynput import keyboard
    except ImportError as exc:
        logger.error(
            "pynput is required for the global hotkey listener. "
            "Install it with: pip install pynput (%s)",
            exc,
        )
        return 1

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
            _focus_hiev()

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
