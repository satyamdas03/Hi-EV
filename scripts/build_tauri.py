"""Build the Hi-EV Tauri desktop wrapper.

This script:
  1. Builds the Vite React/Three.js HUD from web/.
  2. Builds the Tauri Rust app from desktop/src-tauri.
  3. Produces native installers in desktop/src-tauri/target/release/bundle/.

Run:
    python scripts/build_tauri.py
    python scripts/build_tauri.py --dev     # build web and run `tauri dev`

Requirements:
    - Rust + cargo
    - Node + npm
    - Python daemon source in src/ev
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DESKTOP_DIR = ROOT / "desktop"
TAURI_DIR = DESKTOP_DIR / "src-tauri"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command and stream output; raise on non-zero exit."""
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")


def _check_tool(name: str, args: list[str]) -> None:
    """Verify a required tool is on PATH."""
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found on PATH")
    try:
        subprocess.run([name, *args], check=True, capture_output=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"{name} sanity check failed: {exc}") from exc


def build_web() -> None:
    """Build the web frontend so Tauri can bundle web/dist."""
    print("\n== Building web face ==", flush=True)
    _run(["npm", "install"], cwd=WEB_DIR)
    _run(["npm", "run", "build"], cwd=WEB_DIR)


def build_tauri_dev() -> None:
    """Run Tauri in dev mode."""
    print("\n== Starting Tauri dev ==", flush=True)
    _run(["npm", "install"], cwd=DESKTOP_DIR)
    _run(["npm", "run", "tauri:dev"], cwd=DESKTOP_DIR)


def build_tauri_release() -> None:
    """Build Tauri release bundles for the current platform."""
    print("\n== Installing Tauri CLI ==", flush=True)
    _run(["npm", "install"], cwd=DESKTOP_DIR)
    print("\n== Building Tauri release ==", flush=True)
    _run(["npm", "run", "tauri:build"], cwd=DESKTOP_DIR)

    bundle_dir = TAURI_DIR / "target" / "release" / "bundle"
    print(f"\n== Bundles written to {bundle_dir} ==", flush=True)
    for sub in bundle_dir.iterdir():
        if sub.is_dir():
            for f in sub.iterdir():
                if f.is_file():
                    print(f"  {f}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Hi-EV Tauri desktop wrapper")
    parser.add_argument("--dev", action="store_true", help="Run Tauri in dev mode instead of building installers")
    args = parser.parse_args()

    try:
        _check_tool("cargo", ["--version"])
        _check_tool("node", ["--version"])
        _check_tool("npm", ["--version"])

        build_web()

        if args.dev:
            build_tauri_dev()
        else:
            build_tauri_release()

        return 0
    except RuntimeError as exc:
        print(f"Build failed: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
