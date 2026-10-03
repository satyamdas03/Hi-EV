"""Build a Windows executable installer bundle for Hi-EV using PyInstaller.

This bundles:
  - the Python runtime and all project dependencies
  - the Hi-EV daemon (src/ev)
  - the web HUD assets (web/dist)
  - the unified desktop entry point (scripts/desktop_presence.py)

Run:
    python scripts/build_installer.py
    python scripts/build_installer.py --onefile   # also build portable one-file exe
    python scripts/build_installer.py --smoke     # build and run a quick smoke test

Output:
    dist/Hi-EV/                 (one-folder expanded bundle)
    dist/Hi-EV-Portable/        (one-file portable launcher, optional)
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger("ev.build")

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build" / "hiev"
DIST_DIR = ROOT / "dist" / "Hi-EV"
PORTABLE_DIR = ROOT / "dist" / "Hi-EV-Portable"


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


def _common_pyinstaller_args(workpath: Path, distpath: Path, name: str) -> list[str]:
    """Return the shared PyInstaller arguments."""
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ROOT / "scripts" / "desktop_presence.py"),
        "--name",
        name,
        "--distpath",
        str(distpath),
        "--workpath",
        str(workpath),
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
        "--windowed",
        "--icon",
        "NONE",
    ]


def _build_onefolder() -> None:
    """Build the one-folder bundle."""
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)

    args = _common_pyinstaller_args(BUILD_DIR, DIST_DIR.parent, "Hi-EV")
    args.extend(["--onedir"])
    args.extend(_collect_data_args())

    if _run(args) != 0:
        raise RuntimeError("PyInstaller one-folder build failed")

    # PyInstaller occasionally leaves the launcher EXE in the workpath and only
    # copies the _internal directory to distpath. If that happens, copy it over.
    work_exe = BUILD_DIR / "Hi-EV" / "Hi-EV.exe"
    dist_exe = DIST_DIR / "Hi-EV.exe"
    if not dist_exe.exists() and work_exe.exists():
        print(f"Copying launcher from {work_exe} to {dist_exe}", flush=True)
        shutil.copy2(work_exe, dist_exe)

    if not dist_exe.exists():
        raise RuntimeError(f"Launcher EXE not found at {dist_exe}")


def _build_onefile() -> None:
    """Build a single-file portable executable."""
    workpath = BUILD_DIR / "onefile"
    for path in (PORTABLE_DIR, workpath):
        if path.exists():
            shutil.rmtree(path)

    args = _common_pyinstaller_args(workpath, PORTABLE_DIR, "Hi-EV")
    args.extend(["--onefile"])
    args.extend(_collect_data_args())

    if _run(args) != 0:
        raise RuntimeError("PyInstaller one-file build failed")

    if not (PORTABLE_DIR / "Hi-EV.exe").exists():
        raise RuntimeError(f"Portable EXE not found at {PORTABLE_DIR / 'Hi-EV.exe'}")


def _wait_for_health(base_url: str, timeout: float = 30.0) -> dict | None:
    """Poll /health until the daemon responds or timeout elapses."""
    url = f"{base_url}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError as exc:
            logger.debug("Health poll failed: %s", exc)
        time.sleep(0.25)
    return None


def _smoke_test() -> int:
    """Run the one-folder bundle and verify the daemon starts.

    Returns 0 if the bundled EXE starts and responds on /health, 1 if it was
    blocked by antivirus (a common false-positive for unsigned PyInstaller
    executables). Raises on unexpected errors.
    """
    import subprocess as sp

    exe = DIST_DIR / "Hi-EV.exe"
    if not exe.exists():
        raise RuntimeError(f"Cannot smoke test; {exe} not found")

    print(f"\nSmoke test: starting {exe}...", flush=True)
    try:
        proc = sp.Popen(
            [str(exe)],
            cwd=str(DIST_DIR),
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            text=True,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 225:
            print(
                "\nSmoke test skipped: bundled EXE was blocked by antivirus "
                f"({exc}). This is a known false-positive for unsigned PyInstaller executables.",
                flush=True,
            )
            return 1
        raise

    try:
        health = _wait_for_health("http://127.0.0.1:7345", timeout=45.0)
        if health is None:
            raise RuntimeError(
                "Smoke test failed: daemon did not respond on http://127.0.0.1:7345/health. "
                "Check antivirus / Windows Defender (PyInstaller executables often trigger false positives)."
            )
        print(f"Smoke test passed: /health -> {health}", flush=True)
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except sp.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Hi-EV Windows installer bundles")
    parser.add_argument("--onefile", action="store_true", help="also build a one-file portable executable")
    parser.add_argument("--smoke", action="store_true", help="run a quick smoke test after building")
    args = parser.parse_args()

    _ensure_pyinstaller()
    _build_onefolder()
    if args.onefile:
        _build_onefile()

    print("\nBuild complete:")
    print(f"  One-folder bundle: {DIST_DIR}")
    if args.onefile:
        print(f"  Portable executable: {PORTABLE_DIR}")

    if args.smoke:
        _smoke_test()

    print(
        "\nNOTE: Unsigned PyInstaller executables are frequently flagged by antivirus software. "
        "If the smoke test fails with a virus/malware warning, add a temporary exclusion for "
        f"{ROOT}, run the source smoke test with 'python scripts/desktop_presence.py', or sign "
        "the executable for distribution.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
