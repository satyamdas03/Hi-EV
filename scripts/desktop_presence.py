"""Single desktop entry point for Hi-EV.

Launches the local daemon, global hotkey listener, system-tray widget, and
optionally opens the HUD in the default browser. This is the script the Windows
installer shortcuts point at.

Run:
    python scripts/desktop_presence.py
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urljoin

import httpx

from ev.config import get_settings

logger = logging.getLogger("ev.desktop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _project_root() -> Path:
    """Return the repository root from which this script was launched."""
    return Path(__file__).resolve().parent.parent


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


def _start_daemon(settings) -> subprocess.Popen:
    """Start the FastAPI daemon as a child process."""
    root = _project_root()
    # Prefer uvicorn directly so we can capture logs and kill cleanly.
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "ev.server.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(settings.base_url.rsplit(":", 1)[-1].split("/")[0]),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _start_hotkey(settings) -> subprocess.Popen | None:
    """Start the global hotkey listener as a child process."""
    if not settings.global_hotkey_enabled:
        return None
    root = _project_root()
    cmd = [sys.executable, str(root / "scripts" / "global_hotkey.py")]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _start_tray(settings) -> subprocess.Popen | None:
    """Start the system-tray widget as a child process."""
    if not settings.tray_widget_enabled:
        return None
    root = _project_root()
    cmd = [sys.executable, str(root / "scripts" / "tray_widget.py")]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _log_stream(process: subprocess.Popen, prefix: str) -> None:
    """Forward a child process stdout/stderr to our logger."""
    try:
        for line in process.stdout or []:
            logger.info("[%s] %s", prefix, line.rstrip())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Log stream for %s closed: %s", prefix, exc)


def _terminate(process: subprocess.Popen | None) -> None:
    """Gracefully terminate a child process if it is still running."""
    if process is None or process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error terminating child process: %s", exc)


def main() -> int:
    settings = get_settings()
    base_url = settings.base_url

    logger.info("Starting Hi-EV desktop presence.")
    logger.info("Daemon URL: %s", base_url)

    daemon = _start_daemon(settings)
    threading.Thread(target=_log_stream, args=(daemon, "daemon"), daemon=True).start()

    if not _wait_for_daemon(base_url, timeout=30.0):
        logger.error("Daemon did not become ready within 30 seconds.")
        _terminate(daemon)
        return 1

    logger.info("Daemon ready.")

    hotkey = _start_hotkey(settings)
    if hotkey:
        threading.Thread(target=_log_stream, args=(hotkey, "hotkey"), daemon=True).start()

    tray = _start_tray(settings)
    if tray:
        threading.Thread(target=_log_stream, args=(tray, "tray"), daemon=True).start()

    if settings.desktop_auto_open_hud:
        threading.Thread(target=_open_hud, args=(base_url,), daemon=True).start()

    children = [p for p in (daemon, hotkey, tray) if p is not None]

    def _shutdown(signum=None, frame=None) -> None:
        logger.info("Shutting down Hi-EV desktop presence.")
        for child in children:
            _terminate(child)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            for child in children:
                if child.poll() is not None:
                    logger.warning(
                        "Child process exited unexpectedly (code=%s). Shutting down.",
                        child.returncode,
                    )
                    _shutdown()
            time.sleep(1.0)
    except KeyboardInterrupt:
        _shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
