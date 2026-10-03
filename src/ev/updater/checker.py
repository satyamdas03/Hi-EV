"""Check whether a newer Hi-EV release is available on GitHub.

The updater is intentionally read-only: it reports whether an update exists
and points at the installer script. It never downloads or runs code without the
user confirming.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_REPO = "satyamdas03/Hi-EV"
INSTALLER_URL_TEMPLATE = "https://raw.githubusercontent.com/{repo}/{tag}/scripts/install_windows.ps1"
RELEASES_API_URL_TEMPLATE = "https://api.github.com/repos/{repo}/releases/latest"


def _normalize_version(version: str) -> tuple[int, ...]:
    """Turn 'v0.1.0' or '0.1.0' into a comparable tuple of ints."""
    cleaned = version.lstrip("v").strip()
    parts = re.split(r"[.-]", cleaned)
    numeric: list[int] = []
    for part in parts:
        try:
            numeric.append(int(part))
        except ValueError:
            break
    return tuple(numeric)


class UpdateChecker:
    """Compare local version against the latest GitHub release."""

    def __init__(self, repo: str = DEFAULT_REPO):
        self.repo = repo

    @staticmethod
    def current_version() -> str:
        """Read the installed version from pyproject.toml."""
        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent / "pyproject.toml",
            Path(__file__).resolve().parent.parent.parent / "pyproject.toml",
        ]
        for path in candidates:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.startswith("version"):
                        _, _, value = line.partition("=")
                        return value.strip().strip('"').strip("'")
        return "0.0.0"

    async def latest_release(self) -> dict[str, Any]:
        """Query the GitHub releases API for the latest release."""
        url = RELEASES_API_URL_TEMPLATE.format(repo=self.repo)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.warning("Could not check for updates: %s", exc)
            raise UpdateCheckError(f"Could not reach GitHub releases: {exc}") from exc

    async def check(self) -> dict[str, Any]:
        """Return an update status dict with current, latest, and download URL."""
        current = self.current_version()
        try:
            release = await self.latest_release()
        except UpdateCheckError:
            return {
                "update_available": False,
                "current": current,
                "latest": None,
                "url": None,
                "error": "Could not check for updates",
            }

        latest = release.get("tag_name", "")
        url = INSTALLER_URL_TEMPLATE.format(repo=self.repo, tag=latest)
        return {
            "update_available": _normalize_version(latest) > _normalize_version(current),
            "current": current,
            "latest": latest,
            "url": url,
            "error": None,
        }


class UpdateCheckError(Exception):
    """Raised when the update check cannot be completed."""
