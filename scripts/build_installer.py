"""Build a Windows executable installer for Hi-EV using PyInstaller.

This bundles:
  - the Python runtime and all project dependencies
  - the Hi-EV daemon (src/ev)
  - the web HUD assets (web/dist)
  - the unified desktop entry point (scripts/desktop_presence.py)

Run:
    python scripts/build_installer.py

Output:
    build/hiev/H i-EV.exe      (one-file standalone launcher)
    dist/Hi-EV/                 (one-folder expanded bundle)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build" / "hiev"
DIST_DIR = ROOT / "dist" / "Hi-EV"


def _run(cmd: list[str], **kwargs) -> int:
    """Run a command and stream output."""
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, **kwargs).returncode


def _ensure_pyinstaller() -> None:
    """Install PyInstaller if it is not already available."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found; installing...", flush=True)
        if _run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"]) != 0:
            raise RuntimeError("Failed to install PyInstaller")


def _collect_data_args() -> list[str]:
    """Build --add-data entries for web/dist and any runtime resources."""
    web_dist = ROOT / "web" / "dist"
    if not web_dist.is_dir():
        raise RuntimeError(
            f"web/dist not found at {web_dist}. Run 'cd web && npm run build' first."
        )
    separator = ";" if sys.platform == "win32" else ":"
    return ["--add-data", f"{web_dist}{separator}web/dist"]


def _build_onefolder() -> None:
    """Build the one-folder bundle that one-file mode will embed."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    args: list[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "scripts" / "desktop_presence.py"),
        "--name",
        "Hi-EV",
        "--distpath",
        str(DIST_DIR.parent),
        "--workpath",
        str(BUILD_DIR),
        "--paths",
        str(ROOT / "src"),
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "aiosqlite",
        "--hidden-import",
        "sqlite_vec",
        "--hidden-import",
        "pydantic_settings",
        "--hidden-import",
        "sentence_transformers",
        "--hidden-import",
        "httpx",
        "--hidden-import",
        "pkg_resources",
        "--clean",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--icon",
        "NONE",
    ]
    args.extend(_collect_data_args())

    if _run(args) != 0:
        raise RuntimeError("PyInstaller one-folder build failed")


def _build_onefile() -> None:
    """Build a single-file portable executable."""
    onefile_dist = ROOT / "dist" / "Hi-EV-Portable"
    if onefile_dist.exists():
        shutil.rmtree(onefile_dist)

    args: list[str] = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "scripts" / "desktop_presence.py"),
        "--name",
        "Hi-EV",
        "--distpath",
        str(onefile_dist),
        "--workpath",
        str(BUILD_DIR / "onefile"),
        "--paths",
        str(ROOT / "src"),
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "aiosqlite",
        "--hidden-import",
        "sqlite_vec",
        "--hidden-import",
        "pydantic_settings",
        "--hidden-import",
        "sentence_transformers",
        "--hidden-import",
        "httpx",
        "--hidden-import",
        "pkg_resources",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon",
        "NONE",
    ]
    args.extend(_collect_data_args())

    if _run(args) != 0:
        raise RuntimeError("PyInstaller one-file build failed")


def main() -> int:
    _ensure_pyinstaller()
    _build_onefolder()
    _build_onefile()
    print("\nBuild complete:")
    print(f"  One-folder bundle: {DIST_DIR}")
    print(f"  Portable executable: {ROOT / 'dist' / 'Hi-EV-Portable'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
