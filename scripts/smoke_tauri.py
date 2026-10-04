#!/usr/bin/env python3
"""Smoke test for the Tauri desktop wrapper build artifacts.

This script is meant to run after `npm run tauri:build` in the `desktop/`
directory. It verifies that the Windows MSI installer, the native executable,
and the icon assets all exist and look sane. It does *not* install or run the
MSI, because that requires admin rights and a clean Windows environment.

Usage:
    python scripts/smoke_tauri.py
    python scripts/smoke_tauri.py --run   # also launch the dev Tauri app and wait for /health
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
TAURI_DIR = REPO_ROOT / "desktop" / "src-tauri"
TARGET_DIR = TAURI_DIR / "target" / "release"
BUNDLE_DIR = TARGET_DIR / "bundle" / "msi"


def check_artifacts() -> list[str]:
    """Verify the expected build artifacts exist and return a list of errors."""
    errors: list[str] = []

    msis = sorted(BUNDLE_DIR.glob("Hi-EV_*.msi"))
    if not msis:
        errors.append(f"No Hi-EV_*.msi installer found in {BUNDLE_DIR}")
    else:
        for msi in msis:
            size = msi.stat().st_size
            print(f"  [ok] MSI: {msi.name} ({size / 1024 / 1024:.1f} MB)")

    exe = TARGET_DIR / "hi-ev-desktop.exe"
    if not exe.exists():
        errors.append(f"Native executable not found: {exe}")
    else:
        print(f"  [ok] EXE: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MB)")

    required_icons = [
        "32x32.png",
        "128x128.png",
        "128x128@2x.png",
        "icon.png",
        "icon.ico",
        "icon.icns",
    ]
    icon_dir = TAURI_DIR / "icons"
    for name in required_icons:
        path = icon_dir / name
        if not path.exists():
            errors.append(f"Missing icon: {path}")
        elif path.stat().st_size == 0:
            errors.append(f"Empty icon: {path}")
        else:
            print(f"  [ok] icon: {name}")

    return errors


def run_dev_app_and_wait_for_health(timeout_sec: int = 60) -> list[str]:
    """Launch the Tauri app via `cargo run` and wait until /health responds."""
    errors: list[str] = []
    print("Launching Tauri app with `cargo run`...")
    proc = subprocess.Popen(
        ["cargo", "run", "--release"],
        cwd=TAURI_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = "http://127.0.0.1:7345/health"
    start = time.time()
    try:
        while time.time() - start < timeout_sec:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    print(f"  [ok] daemon healthy: {resp.json()}")
                    break
            except requests.RequestException:
                pass
            if proc.poll() is not None:
                errors.append("Tauri app exited before daemon became healthy")
                break
            time.sleep(1)
        else:
            errors.append(f"Daemon did not become healthy within {timeout_sec}s")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Tauri desktop artifacts")
    parser.add_argument("--run", action="store_true", help="Also launch the dev app and wait for /health")
    args = parser.parse_args()

    print("Checking Tauri build artifacts...")
    errors = check_artifacts()

    if args.run:
        errors.extend(run_dev_app_and_wait_for_health())

    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nAll Tauri smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
